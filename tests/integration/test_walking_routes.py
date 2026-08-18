"""Routed walking enrichment + plausibility validation (04 §12)."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.conftest import requires_db

from rental_agent.db.models import Address, TransitAccess, TransitStop
from rental_agent.enrichment.transit.walking import OsrmFootRouter, WalkingEnrichmentService

pytestmark = requires_db


@pytest.fixture()
def primary_candidate(db_session: Session, seeded_source, seeded_listing):
    from datetime import UTC, datetime

    address = db_session.execute(select(Address)).scalar_one()
    address.location_point = "SRID=4326;POINT(-73.9875 40.7555)"
    stop = TransitStop(
        provider_source_id=seeded_source,
        provider_stop_id="S1",
        operator_code="MTA",
        stop_name="Times Sq",
        mode="SUBWAY",
        location_point="SRID=4326;POINT(-73.9870 40.7553)",
        active_status="ACTIVE",
        dataset_version="t1",
    )
    db_session.add(stop)
    db_session.flush()
    access = TransitAccess(
        canonical_listing_id=seeded_listing,
        transit_stop_id=stop.transit_stop_id,
        mode="SUBWAY",
        straight_line_distance_m=65,
        proximity_rank=1,
        usefulness_status="CANDIDATE",
        validation_status="PENDING",
        input_location_hash="h",
        dataset_version="t1",
        calculated_at=datetime.now(tz=UTC),
    )
    db_session.add(access)
    db_session.commit()
    return access


def _router(distance, duration):
    def fetch(url):
        return {"code": "Ok", "routes": [{"distance": distance, "duration": duration}]}

    return OsrmFootRouter(fetcher=fetch)


def test_plausible_route_passes(db_session: Session, primary_candidate):
    service = WalkingEnrichmentService(db_session, _router(90, 70), pace_seconds=0)
    summary = service.enrich_primary_candidates()
    db_session.commit()
    assert summary.routed == 1 and summary.warnings == 0
    db_session.refresh(primary_candidate)
    assert primary_candidate.walking_distance_m == 90
    assert primary_candidate.walking_duration_s == 70
    assert primary_candidate.validation_status == "PASSED"


def test_implausible_speed_warns(db_session: Session, primary_candidate):
    # 900 m in 60 s = 15 m/s — not walking.
    service = WalkingEnrichmentService(db_session, _router(900, 60), pace_seconds=0)
    summary = service.enrich_primary_candidates()
    db_session.commit()
    assert summary.warnings == 1
    db_session.refresh(primary_candidate)
    assert primary_candidate.validation_status == "WARNING"
    assert "implausible_speed" in primary_candidate.validation_reasons["issue"]


def test_routed_shorter_than_straight_line_warns(db_session: Session, primary_candidate):
    # Straight line is 65 m; a routed 10 m walk is geometrically impossible.
    service = WalkingEnrichmentService(db_session, _router(10, 10), pace_seconds=0)
    service.enrich_primary_candidates()
    db_session.commit()
    db_session.refresh(primary_candidate)
    assert primary_candidate.validation_status == "WARNING"
    assert primary_candidate.validation_reasons["issue"] == "routed_shorter_than_straight_line"


def test_provider_failure_leaves_fields_null(db_session: Session, primary_candidate):
    def failing_fetch(url):
        raise TimeoutError("down")

    service = WalkingEnrichmentService(
        db_session, OsrmFootRouter(fetcher=failing_fetch), pace_seconds=0
    )
    summary = service.enrich_primary_candidates()
    db_session.commit()
    assert summary.failed == 1
    db_session.refresh(primary_candidate)
    # Never promote straight-line into a walking claim.
    assert primary_candidate.walking_distance_m is None
    assert primary_candidate.walking_duration_s is None
