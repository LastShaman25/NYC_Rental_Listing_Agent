"""Boundary registry + scope validation (04 §9; PR-GEO-001)."""

from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.conftest import requires_db

from rental_agent.db.models import Address, GeographicBoundary
from rental_agent.enrichment.location.boundaries import (
    ScopeRunSummary,
    upsert_boundary,
    validate_boundaries,
)

pytestmark = requires_db

# A square roughly covering midtown Manhattan.
SQUARE = {
    "type": "Polygon",
    "coordinates": [
        [[-74.02, 40.72], [-73.95, 40.72], [-73.95, 40.78], [-74.02, 40.78], [-74.02, 40.72]]
    ],
}


def _address(db_session, name, lon=None, lat=None) -> Address:
    address = Address(
        address_line_1=name,
        locality="Test",
        administrative_area="NY",
        formatted_address=name,
        location_point=(f"SRID=4326;POINT({lon} {lat})" if lon is not None else None),
    )
    db_session.add(address)
    db_session.flush()
    return address


def test_upsert_is_idempotent(db_session: Session):
    assert upsert_boundary(
        db_session,
        region_code="TEST_SQUARE",
        display_name="Test square",
        region_group="NYC",
        geometry_geojson=SQUARE,
        dataset_version="t1",
    )
    assert not upsert_boundary(
        db_session,
        region_code="TEST_SQUARE",
        display_name="Test square",
        region_group="NYC",
        geometry_geojson=SQUARE,
        dataset_version="t1",
    )
    db_session.commit()
    assert db_session.execute(select(GeographicBoundary)).scalar_one().region_code == "TEST_SQUARE"


def test_scope_validation_sets_statuses_honestly(db_session: Session):
    upsert_boundary(
        db_session,
        region_code="TEST_SQUARE",
        display_name="Test square",
        region_group="NYC",
        geometry_geojson=SQUARE,
        dataset_version="t1",
    )
    inside = _address(db_session, "inside", -73.99, 40.75)
    outside = _address(db_session, "outside", -73.80, 40.60)
    unlocated = _address(db_session, "unlocated")
    db_session.commit()

    summary: ScopeRunSummary = validate_boundaries(db_session)
    db_session.commit()

    assert summary.evaluated == 2
    assert summary.in_scope == 1 and summary.out_of_scope == 1
    db_session.refresh(inside)
    db_session.refresh(outside)
    db_session.refresh(unlocated)
    assert inside.boundary_status == "IN_SCOPE"
    assert outside.boundary_status == "OUT_OF_SCOPE"
    # Unlocated addresses are never silently assigned a scope (PR-GEO-001).
    assert unlocated.boundary_status == "UNRESOLVED"

    # Re-run is a no-op: statuses already decided.
    assert validate_boundaries(db_session).evaluated == 0
