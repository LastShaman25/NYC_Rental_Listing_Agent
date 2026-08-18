"""Fact assertions/resolutions and override precedence (02 §10, §18; schema tests 5, 13)."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.conftest import requires_db

from rental_agent.canonical.normalization import NormalizationService
from rental_agent.contracts import enums as e
from rental_agent.contracts.enums import ParseStatus, RefreshTriggerType
from rental_agent.contracts.fakes import minimal_observation
from rental_agent.db.models import (
    CanonicalListing,
    FactAssertion,
    FactResolution,
    HumanOverride,
    ReviewIssue,
)
from rental_agent.db.repositories.observations import ObservationRepository
from rental_agent.db.repositories.runs import RefreshRunRepository

pytestmark = requires_db

NOW = datetime.now(tz=UTC)


def _persist(
    db_session: Session,
    source_id: uuid.UUID,
    *,
    rent_minor: int = 350000,
    laundry: e.LaundryType = e.LaundryType.BUILDING_SHARED_LAUNDRY,
    content_hash: str | None = None,
    observed_at: datetime = NOW,
) -> uuid.UUID:
    runs = RefreshRunRepository(db_session)
    run_id, _ = runs.create_or_join(
        logical_run_key=f"test:{uuid.uuid4().hex}",
        trigger_type=RefreshTriggerType.MANUAL,
        started_at=observed_at,
        pipeline_version="t1",
    )
    source_run_id = runs.create_source_run(
        refresh_run_id=run_id, source_id=source_id, started_at=observed_at, adapter_version="t1"
    )
    obs = minimal_observation(observed_at=observed_at)
    obs.identity.raw_address_text = "77 Provenance Place"
    obs.identity.source_geographic_labels = ["Manhattan"]
    obs.pricing.monthly_rent_minor = rent_minor
    obs.pricing.source_price_text = f"${rent_minor // 100:,}/month"
    obs.layout.proposed_layout_class = e.LayoutClass.ONE_BEDROOM
    obs.laundry.proposed_laundry_type = laundry
    obs.laundry.evidence_text = "laundry room in building"
    obs_id = ObservationRepository(db_session).insert_idempotent(
        obs,
        source_id=source_id,
        source_run_id=source_run_id,
        content_hash=content_hash or uuid.uuid4().hex,
        parse_status=ParseStatus.PARTIAL,
    )
    db_session.commit()
    assert obs_id is not None
    return obs_id


def test_new_listing_records_assertions_with_single_current_resolution(
    db_session: Session, seeded_source
):
    obs_id = _persist(db_session, seeded_source)
    outcome = NormalizationService(db_session).process_observation(
        obs_id, discovery_method=e.DiscoveryMethod.SEARCH_INDEX
    )
    db_session.commit()

    assertions = db_session.execute(select(FactAssertion)).scalars().all()
    keys = {a.fact_key for a in assertions}
    assert {"monthly_rent_minor", "layout_class", "laundry_type"} <= keys
    rent = next(a for a in assertions if a.fact_key == "monthly_rent_minor")
    assert rent.value_json == {"value": 350000}
    assert rent.evidence_text == "$3,500/month"
    assert rent.source_observation_id == obs_id
    # Exactly one current resolution per fact key.
    for key in keys:
        current = db_session.execute(
            select(func.count())
            .select_from(FactResolution)
            .where(
                FactResolution.entity_id == outcome.canonical_listing_id,
                FactResolution.fact_key == key,
                FactResolution.superseded_at.is_(None),
            )
        ).scalar()
        assert current == 1, key


def test_price_change_supersedes_resolution_keeps_assertion_history(
    db_session: Session, seeded_source
):
    service = NormalizationService(db_session)
    first = _persist(db_session, seeded_source, rent_minor=350000)
    service.process_observation(first, discovery_method=e.DiscoveryMethod.SEARCH_INDEX)
    db_session.commit()
    second = _persist(
        db_session, seeded_source, rent_minor=365000, observed_at=NOW + timedelta(days=1)
    )
    outcome = service.process_observation(second, discovery_method=e.DiscoveryMethod.SEARCH_INDEX)
    db_session.commit()

    rent_assertions = (
        db_session.execute(
            select(FactAssertion)
            .where(FactAssertion.fact_key == "monthly_rent_minor")
            .order_by(FactAssertion.asserted_at)
        )
        .scalars()
        .all()
    )
    assert len(rent_assertions) == 2  # full history retained
    resolutions = (
        db_session.execute(
            select(FactResolution).where(FactResolution.fact_key == "monthly_rent_minor")
        )
        .scalars()
        .all()
    )
    current = [r for r in resolutions if r.superseded_at is None]
    assert len(resolutions) == 2 and len(current) == 1
    assert current[0].effective_assertion_id == rent_assertions[-1].fact_assertion_id
    listing = db_session.get(CanonicalListing, outcome.canonical_listing_id)
    assert listing.monthly_rent_minor == 365000


def test_active_override_survives_refresh_and_raises_conflict(db_session: Session, seeded_source):
    service = NormalizationService(db_session)
    first = _persist(db_session, seeded_source, rent_minor=350000)
    outcome = service.process_observation(first, discovery_method=e.DiscoveryMethod.SEARCH_INDEX)
    db_session.commit()

    # Operator corrects the rent and locks it with an active override.
    listing = db_session.get(CanonicalListing, outcome.canonical_listing_id)
    listing.monthly_rent_minor = 340000
    db_session.add(
        HumanOverride(
            entity_type="LISTING",
            entity_id=listing.canonical_listing_id,
            field_name="monthly_rent_minor",
            override_value={"value": 340000},
            reason_code="SOURCE_ERROR",
            reason_text="source shows net-effective; corrected to gross",
            created_by="local_operator",
        )
    )
    db_session.commit()

    # A later refresh observes a different rent.
    second = _persist(
        db_session, seeded_source, rent_minor=380000, observed_at=NOW + timedelta(days=1)
    )
    result = service.process_observation(second, discovery_method=e.DiscoveryMethod.SEARCH_INDEX)
    db_session.commit()

    listing = db_session.get(CanonicalListing, outcome.canonical_listing_id)
    assert listing.monthly_rent_minor == 340000  # override NOT overwritten
    assert "PRICE_CHANGED" not in result.events_emitted
    issue = db_session.execute(
        select(ReviewIssue).where(ReviewIssue.issue_type == "CONFLICT")
    ).scalar_one()
    assert issue.details["fact_key"] == "monthly_rent_minor"
    assert issue.details["incoming_value"] == 380000
    # Evidence still recorded despite the override (auditability).
    rent_assertions = db_session.execute(
        select(func.count())
        .select_from(FactAssertion)
        .where(FactAssertion.fact_key == "monthly_rent_minor")
    ).scalar()
    assert rent_assertions == 2

    # A third conflicting refresh does not spam duplicate open issues.
    third = _persist(
        db_session, seeded_source, rent_minor=390000, observed_at=NOW + timedelta(days=2)
    )
    service.process_observation(third, discovery_method=e.DiscoveryMethod.SEARCH_INDEX)
    db_session.commit()
    open_conflicts = db_session.execute(
        select(func.count())
        .select_from(ReviewIssue)
        .where(ReviewIssue.issue_type == "CONFLICT", ReviewIssue.status == "OPEN")
    ).scalar()
    assert open_conflicts == 1


def test_laundry_change_updates_type_but_badge_stays_conservative(
    db_session: Session, seeded_source
):
    service = NormalizationService(db_session)
    first = _persist(db_session, seeded_source, laundry=e.LaundryType.BUILDING_SHARED_LAUNDRY)
    outcome = service.process_observation(first, discovery_method=e.DiscoveryMethod.SEARCH_INDEX)
    db_session.commit()
    second = _persist(
        db_session,
        seeded_source,
        laundry=e.LaundryType.IN_UNIT_WASHER_DRYER_CONFIRMED,
        observed_at=NOW + timedelta(days=1),
    )
    result = service.process_observation(second, discovery_method=e.DiscoveryMethod.SEARCH_INDEX)
    db_session.commit()

    assert "LAUNDRY_CHANGED" in result.events_emitted
    listing = db_session.get(CanonicalListing, outcome.canonical_listing_id)
    assert listing.laundry_type == "IN_UNIT_WASHER_DRYER_CONFIRMED"
    # Snippet evidence is unvalidated (PENDING) — 室内洗烘 badge must stay false.
    assert listing.indoor_laundry_badge_eligible is False
