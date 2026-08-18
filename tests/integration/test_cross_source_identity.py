"""Cross-source identity: exact attach vs reviewable duplicate candidates
(02 §9.1 hierarchy step 2, §9.3 conservative merges; schema tests 2–3)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.conftest import requires_db

from rental_agent.canonical.normalization import NormalizationService, unit_fingerprint
from rental_agent.contracts import enums as e
from rental_agent.contracts.enums import ParseStatus, RefreshTriggerType
from rental_agent.contracts.fakes import minimal_observation
from rental_agent.db.models import (
    CanonicalListing,
    DuplicateCandidate,
    ListingSourceLink,
    Source,
    Unit,
)
from rental_agent.db.repositories.observations import ObservationRepository
from rental_agent.db.repositories.runs import RefreshRunRepository

pytestmark = requires_db

NOW = datetime.now(tz=UTC)


def _second_source(db_session: Session) -> uuid.UUID:
    source = Source(
        source_code=f"other_source_{uuid.uuid4().hex[:8]}",
        display_name="Other Source",
        source_type="LISTING",
        access_method="MANUAL_IMPORT",
        policy_version="test-0",
    )
    db_session.add(source)
    db_session.commit()
    return source.source_id


def _persist(
    db_session: Session,
    source_id: uuid.UUID,
    *,
    url: str,
    native_id: str,
    address: str,
    unit_label: str | None = None,
    rent_minor: int | None = 350000,
    layout: e.LayoutClass = e.LayoutClass.ONE_BEDROOM,
) -> uuid.UUID:
    runs = RefreshRunRepository(db_session)
    run_id, _ = runs.create_or_join(
        logical_run_key=f"test:{uuid.uuid4().hex}",
        trigger_type=RefreshTriggerType.MANUAL,
        started_at=NOW,
        pipeline_version="t1",
    )
    source_run_id = runs.create_source_run(
        refresh_run_id=run_id, source_id=source_id, started_at=NOW, adapter_version="t1"
    )
    obs = minimal_observation(source_url=url, source_native_id=native_id, observed_at=NOW)
    obs.identity.raw_address_text = address
    obs.identity.raw_unit_label = unit_label
    obs.identity.source_geographic_labels = ["Manhattan"]
    obs.pricing.monthly_rent_minor = rent_minor
    obs.layout.proposed_layout_class = layout
    obs_id = ObservationRepository(db_session).insert_idempotent(
        obs,
        source_id=source_id,
        source_run_id=source_run_id,
        content_hash=uuid.uuid4().hex,
        parse_status=ParseStatus.PARTIAL,
    )
    db_session.commit()
    assert obs_id is not None
    return obs_id


def test_unit_fingerprint_variants():
    assert unit_fingerprint("4A") == unit_fingerprint("APT 4A") == unit_fingerprint("#4-a")
    assert unit_fingerprint("4A") != unit_fingerprint("4B")


def test_same_building_and_unit_attaches_second_source(db_session: Session, seeded_source):
    service = NormalizationService(db_session)
    first = _persist(
        db_session,
        seeded_source,
        url="https://a.test/1",
        native_id="A1",
        address="225 East 34th Street",
        unit_label="12B",
    )
    outcome1 = service.process_observation(first, discovery_method=e.DiscoveryMethod.SEARCH_INDEX)
    db_session.commit()

    other = _second_source(db_session)
    second = _persist(
        db_session,
        other,
        url="https://b.test/9",
        native_id="B9",
        address="225 E 34th St.",  # syntactic variant, same building
        unit_label="APT 12-B",  # syntactic variant, same unit
    )
    outcome2 = service.process_observation(second, discovery_method=e.DiscoveryMethod.DIRECT)
    db_session.commit()

    assert outcome2.classification == "MATCHED_EXISTING"
    assert outcome2.canonical_listing_id == outcome1.canonical_listing_id
    assert db_session.execute(select(func.count()).select_from(CanonicalListing)).scalar() == 1
    links = db_session.execute(select(ListingSourceLink)).scalars().all()
    assert len(links) == 2  # separate provenance retained (PR-ACQ-003)
    methods = {link.identity_method for link in links}
    assert "EXACT_ADDRESS_AND_UNIT" in methods
    assert db_session.execute(select(func.count()).select_from(Unit)).scalar() == 1
    assert db_session.execute(select(func.count()).select_from(DuplicateCandidate)).scalar() == 0


def test_similar_listing_without_unit_becomes_duplicate_candidate(
    db_session: Session, seeded_source
):
    service = NormalizationService(db_session)
    first = _persist(
        db_session,
        seeded_source,
        url="https://a.test/1",
        native_id="A1",
        address="100 Water Street",
        rent_minor=350000,
    )
    service.process_observation(first, discovery_method=e.DiscoveryMethod.SEARCH_INDEX)
    db_session.commit()

    other = _second_source(db_session)
    second = _persist(
        db_session,
        other,
        url="https://b.test/2",
        native_id="B2",
        address="100 Water St",
        rent_minor=353000,  # within 2% tolerance
    )
    outcome = service.process_observation(second, discovery_method=e.DiscoveryMethod.DIRECT)
    db_session.commit()

    # Conservative: no auto-merge — two listings plus one PENDING review candidate.
    assert outcome.classification == "NEW"
    assert db_session.execute(select(func.count()).select_from(CanonicalListing)).scalar() == 2
    candidate = db_session.execute(select(DuplicateCandidate)).scalar_one()
    assert candidate.status == "PENDING"
    assert candidate.evidence["rule"] == "same_building_layout_similar_rent"


def test_dissimilar_listings_create_no_candidate(db_session: Session, seeded_source):
    service = NormalizationService(db_session)
    first = _persist(
        db_session,
        seeded_source,
        url="https://a.test/1",
        native_id="A1",
        address="100 Water Street",
        rent_minor=350000,
    )
    service.process_observation(first, discovery_method=e.DiscoveryMethod.SEARCH_INDEX)
    db_session.commit()

    other = _second_source(db_session)
    second = _persist(
        db_session,
        other,
        url="https://b.test/2",
        native_id="B2",
        address="100 Water St",
        rent_minor=520000,  # far outside tolerance
    )
    service.process_observation(second, discovery_method=e.DiscoveryMethod.DIRECT)
    db_session.commit()
    assert db_session.execute(select(func.count()).select_from(DuplicateCandidate)).scalar() == 0


def test_candidate_generation_is_replay_safe(db_session: Session, seeded_source):
    service = NormalizationService(db_session)
    first = _persist(
        db_session,
        seeded_source,
        url="https://a.test/1",
        native_id="A1",
        address="100 Water Street",
    )
    other = _second_source(db_session)
    second = _persist(
        db_session,
        other,
        url="https://b.test/2",
        native_id="B2",
        address="100 Water St",
        rent_minor=353000,  # similar but NOT identical -> candidate, not strong match
    )
    service.process_observation(first, discovery_method=e.DiscoveryMethod.SEARCH_INDEX)
    service.process_observation(second, discovery_method=e.DiscoveryMethod.DIRECT)
    db_session.commit()
    # Replays: no duplicate candidates, listings, or links appear.
    service.process_observation(second, discovery_method=e.DiscoveryMethod.DIRECT)
    db_session.commit()
    assert db_session.execute(select(func.count()).select_from(DuplicateCandidate)).scalar() == 1
    assert db_session.execute(select(func.count()).select_from(CanonicalListing)).scalar() == 2


def test_strong_multi_field_attaches_identical_listing(db_session: Session, seeded_source):
    """Same building + same layout + IDENTICAL rent + no unit labels anywhere ->
    one canonical listing with a MEDIUM-confidence STRONG_MULTI_FIELD link."""
    service = NormalizationService(db_session)
    first = _persist(
        db_session,
        seeded_source,
        url="https://a.test/1",
        native_id="A1",
        address="200 Strong Street",
        rent_minor=350000,
    )
    outcome1 = service.process_observation(first, discovery_method=e.DiscoveryMethod.SEARCH_INDEX)
    db_session.commit()
    other = _second_source(db_session)
    second = _persist(
        db_session,
        other,
        url="https://b.test/2",
        native_id="B2",
        address="200 Strong St",
        rent_minor=350000,
    )
    outcome2 = service.process_observation(second, discovery_method=e.DiscoveryMethod.DIRECT)
    db_session.commit()
    assert outcome2.classification == "MATCHED_EXISTING"
    assert outcome2.canonical_listing_id == outcome1.canonical_listing_id
    assert db_session.execute(select(func.count()).select_from(CanonicalListing)).scalar() == 1
    links = db_session.execute(select(ListingSourceLink)).scalars().all()
    methods = {link.identity_method for link in links}
    assert "STRONG_MULTI_FIELD" in methods
    strong_link = next(x for x in links if x.identity_method == "STRONG_MULTI_FIELD")
    assert strong_link.identity_confidence == "MEDIUM"


def test_strong_match_refuses_ambiguity(db_session: Session, seeded_source):
    """TWO identical same-building listings -> ambiguous; no auto-attach."""
    service = NormalizationService(db_session)
    for i, native in enumerate(["A1", "A2"]):
        obs = _persist(
            db_session,
            seeded_source,
            url=f"https://a.test/{i}",
            native_id=native,
            address="300 Ambiguous Avenue",
            rent_minor=400000,
        )
        service.process_observation(obs, discovery_method=e.DiscoveryMethod.SEARCH_INDEX)
        db_session.commit()
    other = _second_source(db_session)
    third = _persist(
        db_session,
        other,
        url="https://b.test/9",
        native_id="B9",
        address="300 Ambiguous Ave",
        rent_minor=400000,
    )
    outcome = service.process_observation(third, discovery_method=e.DiscoveryMethod.DIRECT)
    db_session.commit()
    # Ambiguity -> a third listing plus review candidates, never a guess.
    assert outcome.classification == "NEW"
    assert db_session.execute(select(func.count()).select_from(CanonicalListing)).scalar() == 3
