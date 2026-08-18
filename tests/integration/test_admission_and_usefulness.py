"""Admission (02 §22.1) and transit usefulness v1 (04 §13)."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.conftest import requires_db

from rental_agent.canonical.admission import AdmissionService
from rental_agent.db.models import (
    Address,
    Building,
    CanonicalListing,
    ListingEvent,
    ListingSourceLink,
    RefreshRun,
    SourceObservation,
    SourceRun,
    TransitAccess,
    TransitStop,
)
from rental_agent.enrichment.transit.usefulness import classify_usefulness

pytestmark = requires_db

NOW = datetime.now(tz=UTC)


def _listing(
    db_session: Session,
    seeded_source,
    *,
    layout="ONE_BEDROOM",
    boundary="IN_SCOPE",
    precision="BUILDING",
    with_link=True,
) -> CanonicalListing:
    address = Address(
        address_line_1=f"addr-{uuid.uuid4().hex[:6]}",
        locality="Manhattan",
        administrative_area="NY",
        formatted_address=f"addr-{uuid.uuid4().hex[:6]}",
        boundary_status=boundary,
        location_precision=precision,
    )
    db_session.add(address)
    db_session.flush()
    building = Building(address_id=address.address_id)
    db_session.add(building)
    db_session.flush()
    listing = CanonicalListing(
        building_id=building.building_id,
        layout_class=layout,
        first_seen_at=NOW,
        last_seen_at=NOW,
        last_material_change_at=NOW,
    )
    db_session.add(listing)
    db_session.flush()
    if with_link:
        run = RefreshRun(
            trigger_type="MANUAL",
            logical_run_key=f"t:{uuid.uuid4().hex}",
            started_at=NOW,
            pipeline_version="t",
        )
        db_session.add(run)
        db_session.flush()
        source_run = SourceRun(
            refresh_run_id=run.refresh_run_id,
            source_id=seeded_source,
            started_at=NOW,
            adapter_version="t",
        )
        db_session.add(source_run)
        db_session.flush()
        observation = SourceObservation(
            source_id=seeded_source,
            source_run_id=source_run.source_run_id,
            source_native_id=uuid.uuid4().hex[:8],
            source_url=f"https://t.test/{uuid.uuid4().hex[:8]}",
            observed_at=NOW,
            retrieved_at=NOW,
            content_hash=uuid.uuid4().hex,
            parsed_payload={},
            parse_status="PARTIAL",
            contact_redaction_status="NOT_PRESENT",
            adapter_version="t",
            schema_version="1",
        )
        db_session.add(observation)
        db_session.flush()
        db_session.add(
            ListingSourceLink(
                canonical_listing_id=listing.canonical_listing_id,
                source_id=seeded_source,
                source_native_id=observation.source_native_id,
                source_url=observation.source_url,
                first_observation_id=observation.source_observation_id,
                latest_observation_id=observation.source_observation_id,
                first_seen_at=NOW,
                last_seen_at=NOW,
                link_status="ACTIVE",
                identity_method="SOURCE_NATIVE_CONTINUITY",
                identity_confidence="HIGH",
                identity_rule_version="t",
            )
        )
    db_session.commit()
    return listing


def test_admissible_listing_activates(db_session: Session, seeded_source):
    listing = _listing(db_session, seeded_source)
    summary = AdmissionService(db_session).evaluate_candidates()
    db_session.commit()
    assert summary.activated == 1
    db_session.refresh(listing)
    assert listing.lifecycle_status == "ACTIVE"
    event = db_session.execute(
        select(ListingEvent).where(ListingEvent.event_type == "ACTIVATED")
    ).scalar_one()
    assert event.canonical_listing_id == listing.canonical_listing_id


def test_out_of_scope_layout_and_geography_are_excluded(db_session: Session, seeded_source):
    a = _listing(db_session, seeded_source, layout="OUT_OF_SCOPE")
    b = _listing(db_session, seeded_source, boundary="OUT_OF_SCOPE")
    summary = AdmissionService(db_session).evaluate_candidates()
    db_session.commit()
    assert summary.excluded == 2
    db_session.refresh(a)
    db_session.refresh(b)
    assert a.lifecycle_status == "EXCLUDED"
    assert b.lifecycle_status == "EXCLUDED"


def test_unknowns_are_held_never_admitted_optimistically(db_session: Session, seeded_source):
    _listing(db_session, seeded_source, layout="UNKNOWN")
    _listing(db_session, seeded_source, boundary="UNRESOLVED")
    _listing(db_session, seeded_source, precision="NEIGHBORHOOD")
    _listing(db_session, seeded_source, with_link=False)
    summary = AdmissionService(db_session).evaluate_candidates()
    db_session.commit()
    assert summary.activated == 0
    assert summary.excluded == 0
    assert summary.still_candidate == 4
    assert set(summary.reasons_held) == {
        "layout_unresolved",
        "geography_unresolved",
        "precision_insufficient",
        "no_active_source_link",
    }


def test_admission_rerun_is_idempotent(db_session: Session, seeded_source):
    _listing(db_session, seeded_source)
    service = AdmissionService(db_session)
    service.evaluate_candidates()
    db_session.commit()
    summary = service.evaluate_candidates()
    db_session.commit()
    assert summary.evaluated == 0  # ACTIVE listings are not re-evaluated
    events = db_session.execute(select(ListingEvent)).scalars().all()
    assert len(events) == 1


@pytest.fixture()
def access_rows(db_session: Session, seeded_source, seeded_listing):
    stop = TransitStop(
        provider_source_id=seeded_source,
        provider_stop_id="S1",
        operator_code="MTA",
        stop_name="Near Stop",
        mode="SUBWAY",
        location_point="SRID=4326;POINT(-73.99 40.75)",
        active_status="ACTIVE",
        dataset_version="t1",
    )
    db_session.add(stop)
    db_session.flush()

    def access(meters):
        return TransitAccess(
            canonical_listing_id=seeded_listing,
            transit_stop_id=stop.transit_stop_id,
            mode="SUBWAY",
            straight_line_distance_m=meters,
            usefulness_status="CANDIDATE",
            validation_status="PENDING",
            input_location_hash="h",
            dataset_version="t1",
            calculated_at=NOW,
        )

    db_session.add_all([access(300), access(1500)])
    db_session.commit()


def test_usefulness_v1_thresholds(db_session: Session, access_rows):
    summary = classify_usefulness(db_session)
    db_session.commit()
    assert summary.evaluated == 2
    assert summary.useful == 1  # 300 m within band; 1500 m stays candidate
    rows = db_session.execute(select(TransitAccess)).scalars().all()
    useful = next(r for r in rows if r.usefulness_status == "USEFUL")
    held = next(r for r in rows if r.usefulness_status == "CANDIDATE")
    assert useful.usefulness_reasons["reasons"] == ["DIRECT_SUBWAY_ACCESS"]
    assert useful.usefulness_reasons["distance_basis"] == "straight_line_only"
    assert held.usefulness_reasons["reasons"] == ["SERVICE_UNVERIFIED"]
