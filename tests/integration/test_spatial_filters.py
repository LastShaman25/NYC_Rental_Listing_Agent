"""Spatial inventory filters: bounds and drawn GeoJSON geometry (08 §16.2)."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session
from tests.conftest import requires_db

from rental_agent.db.models import Address, Building, CanonicalListing
from rental_agent.ui import queries

pytestmark = requires_db

NOW = datetime.now(tz=UTC)


@pytest.fixture()
def spread_listings(db_session: Session):
    """Three listings: Manhattan, Brooklyn, and one without coordinates."""
    spots = [
        ("Manhattan spot", -73.985, 40.75),
        ("Brooklyn spot", -73.95, 40.65),
        ("No-coords spot", None, None),
    ]
    for name, lon, lat in spots:
        address = Address(
            address_line_1=name,
            locality="New York",
            administrative_area="NY",
            formatted_address=name,
            location_point=(f"SRID=4326;POINT({lon} {lat})" if lon is not None else None),
            location_precision="BUILDING" if lon is not None else "UNKNOWN",
        )
        db_session.add(address)
        db_session.flush()
        building = Building(address_id=address.address_id)
        db_session.add(building)
        db_session.flush()
        db_session.add(
            CanonicalListing(
                building_id=building.building_id,
                layout_class="STUDIO",
                first_seen_at=NOW,
                last_seen_at=NOW,
                last_material_change_at=NOW,
            )
        )
    db_session.commit()


def test_bounds_filter_limits_to_envelope(db_session: Session, spread_listings):
    # Envelope around midtown Manhattan only.
    rows = queries.inventory(
        db_session,
        queries.InventoryFilters(bounds=(-74.02, 40.70, -73.95, 40.80)),
    )
    assert [r["address"] for r in rows] == ["Manhattan spot"]


def test_drawn_polygon_filter(db_session: Session, spread_listings):
    polygon = {
        "type": "Polygon",
        "coordinates": [
            [[-73.99, 40.60], [-73.90, 40.60], [-73.90, 40.70], [-73.99, 40.70], [-73.99, 40.60]]
        ],
    }
    rows = queries.inventory(db_session, queries.InventoryFilters(geometry_geojson=polygon))
    assert [r["address"] for r in rows] == ["Brooklyn spot"]


def test_spatial_filter_never_matches_unlocated_listings(db_session: Session, spread_listings):
    # A huge polygon still excludes the listing without coordinates: an
    # unlocated listing is never treated as being anywhere.
    polygon = {
        "type": "Polygon",
        "coordinates": [[[-80, 35], [-70, 35], [-70, 45], [-80, 45], [-80, 35]]],
    }
    rows = queries.inventory(db_session, queries.InventoryFilters(geometry_geojson=polygon))
    names = {r["address"] for r in rows}
    assert names == {"Manhattan spot", "Brooklyn spot"}
    # Without spatial filters, all three appear.
    all_rows = queries.inventory(db_session, queries.InventoryFilters())
    assert len(all_rows) == 3
