"""Phase 3 skeleton: observation → canonical normalization (02 §27 tests 1, 5)."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.conftest import requires_db

from rental_agent.canonical.normalization import NormalizationService, address_fingerprint
from rental_agent.contracts import enums as e
from rental_agent.contracts.enums import ParseStatus, RefreshTriggerType
from rental_agent.contracts.fakes import minimal_observation
from rental_agent.db.models import (
    Building,
    CanonicalListing,
    ListingEvent,
    ListingSourceLink,
)
from rental_agent.db.repositories.observations import ObservationRepository
from rental_agent.db.repositories.runs import RefreshRunRepository

pytestmark = requires_db

NOW = datetime.now(tz=UTC)


def _persist_observation(
    db_session: Session,
    source_id: uuid.UUID,
    *,
    rent_minor: int | None = 350000,
    content_hash: str = "h1",
    observed_at: datetime = NOW,
    address: str | None = "225 East 34th Street",
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
    obs.pricing.monthly_rent_minor = rent_minor
    obs.identity.raw_address_text = address
    obs.identity.source_geographic_labels = ["Manhattan"]
    obs.layout.proposed_layout_class = e.LayoutClass.ONE_BEDROOM
    obs_id = ObservationRepository(db_session).insert_idempotent(
        obs,
        source_id=source_id,
        source_run_id=source_run_id,
        content_hash=content_hash,
        parse_status=ParseStatus.PARTIAL,
    )
    db_session.commit()
    assert obs_id is not None
    return obs_id


def test_new_observation_creates_canonical_chain(db_session: Session, seeded_source):
    obs_id = _persist_observation(db_session, seeded_source)
    outcome = NormalizationService(db_session).process_observation(
        obs_id, discovery_method=e.DiscoveryMethod.SEARCH_INDEX
    )
    db_session.commit()
    assert outcome.classification == "NEW"
    listing = db_session.get(CanonicalListing, outcome.canonical_listing_id)
    assert listing.layout_class == "ONE_BEDROOM"
    assert listing.monthly_rent_minor == 350000
    assert listing.lifecycle_status == "CANDIDATE"  # admission comes later, not auto-ACTIVE
    link = db_session.get(ListingSourceLink, outcome.listing_source_link_id)
    assert link.discovery_method == "SEARCH_INDEX"
    building = db_session.get(Building, listing.building_id)
    assert building is not None
    events = db_session.execute(select(ListingEvent)).scalars().all()
    assert [ev.event_type for ev in events] == ["CREATED"]


def test_replay_is_idempotent(db_session: Session, seeded_source):
    obs_id = _persist_observation(db_session, seeded_source)
    service = NormalizationService(db_session)
    first = service.process_observation(obs_id, discovery_method=e.DiscoveryMethod.SEARCH_INDEX)
    db_session.commit()
    second = service.process_observation(obs_id, discovery_method=e.DiscoveryMethod.SEARCH_INDEX)
    db_session.commit()
    assert second.classification == "UNCHANGED"
    assert second.canonical_listing_id == first.canonical_listing_id
    assert db_session.execute(select(func.count()).select_from(CanonicalListing)).scalar() == 1
    assert db_session.execute(select(func.count()).select_from(ListingEvent)).scalar() == 1


def test_unchanged_reobservation_updates_freshness_without_history(
    db_session: Session, seeded_source
):
    later = NOW + timedelta(days=1)
    first_id = _persist_observation(db_session, seeded_source, content_hash="h1")
    second_id = _persist_observation(
        db_session, seeded_source, content_hash="h1", observed_at=later
    )
    service = NormalizationService(db_session)
    service.process_observation(first_id, discovery_method=e.DiscoveryMethod.SEARCH_INDEX)
    db_session.commit()
    outcome = service.process_observation(
        second_id, discovery_method=e.DiscoveryMethod.SEARCH_INDEX
    )
    db_session.commit()
    assert outcome.classification == "UNCHANGED"
    link = db_session.execute(select(ListingSourceLink)).scalar_one()
    assert link.last_seen_at == later  # freshness advanced
    assert db_session.execute(select(func.count()).select_from(ListingEvent)).scalar() == 1


def test_price_change_creates_event_and_updates_materialized_rent(
    db_session: Session, seeded_source
):
    later = NOW + timedelta(days=1)
    first_id = _persist_observation(db_session, seeded_source, rent_minor=350000)
    second_id = _persist_observation(
        db_session, seeded_source, rent_minor=365000, content_hash="h2", observed_at=later
    )
    service = NormalizationService(db_session)
    service.process_observation(first_id, discovery_method=e.DiscoveryMethod.SEARCH_INDEX)
    db_session.commit()
    outcome = service.process_observation(
        second_id, discovery_method=e.DiscoveryMethod.SEARCH_INDEX
    )
    db_session.commit()
    assert outcome.classification == "MATERIAL_CHANGE"
    assert outcome.events_emitted == ["PRICE_CHANGED"]
    listing = db_session.get(CanonicalListing, outcome.canonical_listing_id)
    assert listing.monthly_rent_minor == 365000
    assert listing.last_material_change_at == later
    event = db_session.execute(
        select(ListingEvent).where(ListingEvent.event_type == "PRICE_CHANGED")
    ).scalar_one()
    assert event.before_values == {"monthly_rent_minor": 350000}
    assert event.after_values == {"monthly_rent_minor": 365000}


def test_same_address_reuses_building(db_session: Session, seeded_source):
    a = _persist_observation(db_session, seeded_source, address="225 East 34th Street")
    service = NormalizationService(db_session)
    service.process_observation(a, discovery_method=e.DiscoveryMethod.SEARCH_INDEX)
    db_session.commit()

    # Different source listing at a syntactic variant of the same address.
    obs = minimal_observation(
        source_url="https://example.test/listing/2",
        source_native_id="L2",
        observed_at=NOW,
    )
    obs.identity.raw_address_text = "225 E 34th St."
    obs.identity.source_geographic_labels = ["Manhattan"]
    runs = RefreshRunRepository(db_session)
    run_id, _ = runs.create_or_join(
        logical_run_key=f"test:{uuid.uuid4().hex}",
        trigger_type=RefreshTriggerType.MANUAL,
        started_at=NOW,
        pipeline_version="t1",
    )
    source_run_id = runs.create_source_run(
        refresh_run_id=run_id, source_id=seeded_source, started_at=NOW, adapter_version="t1"
    )
    b = ObservationRepository(db_session).insert_idempotent(
        obs,
        source_id=seeded_source,
        source_run_id=source_run_id,
        content_hash="hx",
        parse_status=ParseStatus.PARTIAL,
    )
    db_session.commit()
    service.process_observation(b, discovery_method=e.DiscoveryMethod.SEARCH_INDEX)
    db_session.commit()
    # Two listings, one shared building via the address fingerprint.
    assert db_session.execute(select(func.count()).select_from(CanonicalListing)).scalar() == 2
    assert db_session.execute(select(func.count()).select_from(Building)).scalar() == 1


def test_address_fingerprint_normalizes_variants():
    assert address_fingerprint("225 East 34th Street") == address_fingerprint("225 E 34th St.")
    assert address_fingerprint("100 Water St") != address_fingerprint("102 Water St")
