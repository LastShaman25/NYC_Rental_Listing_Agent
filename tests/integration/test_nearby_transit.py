"""Nearby-transit candidate generation (04 §11)."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.conftest import requires_db

from rental_agent.db.models import Address, TransitAccess, TransitStop
from rental_agent.enrichment.transit.nearby import NearbyTransitService

pytestmark = requires_db

# Times Sq area listing; one close subway complex, one far, one PATH platform child.
LISTING_POINT = (-73.9875, 40.7555)


@pytest.fixture()
def transit_world(db_session: Session, seeded_source, seeded_listing):
    # Attach coordinates to the seeded listing's address.
    address = db_session.execute(select(Address)).scalar_one()
    address.location_point = f"SRID=4326;POINT({LISTING_POINT[0]} {LISTING_POINT[1]})"
    address.location_precision = "BUILDING"

    def stop(pid, name, mode, lon, lat, parent=None, active="ACTIVE"):
        row = TransitStop(
            provider_source_id=seeded_source,
            provider_stop_id=pid,
            operator_code="MTA" if mode == "SUBWAY" else "PATH",
            stop_name=name,
            mode=mode,
            location_point=f"SRID=4326;POINT({lon} {lat})",
            active_status=active,
            dataset_version="t1",
            parent_stop_id=parent,
        )
        db_session.add(row)
        db_session.flush()
        return row

    stop("S1", "Times Sq-42 St", "SUBWAY", -73.9870, 40.7553)  # ~65 m
    stop("S2", "Grand Central-42 St", "SUBWAY", -73.9772, 40.7527)  # ~920 m
    stop("S3", "Far Rockaway", "SUBWAY", -73.75, 40.60)  # far outside radius
    stop("S4", "Closed Stop", "SUBWAY", -73.9880, 40.7550, active="INACTIVE")
    path_parent = stop("P1", "33 St PATH", "PATH", -73.9880, 40.7490)
    stop(
        "P1N", "33 St PATH platform", "PATH", -73.9880, 40.7490, parent=path_parent.transit_stop_id
    )
    db_session.commit()
    return seeded_listing


def test_candidates_within_radius_ranked_by_distance(db_session: Session, transit_world):
    service = NearbyTransitService(db_session)
    created = service.enrich_listing(transit_world)
    db_session.commit()
    # 2 subway complexes in radius (near + grand central); far + inactive excluded;
    # PATH parent only (platform child excluded).
    assert created == 3
    rows = (
        db_session.execute(
            select(TransitAccess).order_by(TransitAccess.mode, TransitAccess.proximity_rank)
        )
        .scalars()
        .all()
    )
    subway = [r for r in rows if r.mode == "SUBWAY"]
    path = [r for r in rows if r.mode == "PATH"]
    assert len(subway) == 2 and len(path) == 1
    assert subway[0].proximity_rank == 1
    assert subway[0].straight_line_distance_m < subway[1].straight_line_distance_m
    assert subway[0].straight_line_distance_m < 150  # Times Sq is ~65 m away
    # Honesty: no walking claims, candidates only, validation pending.
    assert all(r.walking_distance_m is None and r.walking_duration_s is None for r in rows)
    assert all(r.usefulness_status == "CANDIDATE" for r in rows)
    assert all(r.validation_status == "PENDING" for r in rows)


def test_rerun_with_unchanged_origin_is_noop(db_session: Session, transit_world):
    service = NearbyTransitService(db_session)
    service.enrich_listing(transit_world)
    db_session.commit()
    assert service.enrich_listing(transit_world) == 0
    db_session.commit()
    assert db_session.execute(select(func.count()).select_from(TransitAccess)).scalar() == 3


def test_moved_origin_invalidates_and_regenerates(db_session: Session, transit_world):
    service = NearbyTransitService(db_session)
    service.enrich_listing(transit_world)
    db_session.commit()
    address = db_session.execute(select(Address)).scalar_one()
    address.location_point = "SRID=4326;POINT(-73.9772 40.7527)"  # moved to Grand Central
    db_session.commit()
    created = service.enrich_listing(transit_world)
    db_session.commit()
    assert created > 0
    hashes = set(db_session.execute(select(TransitAccess.input_location_hash)).scalars().all())
    assert len(hashes) == 1  # old-origin rows fully replaced (02 §21)
