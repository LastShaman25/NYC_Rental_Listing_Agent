"""GTFS static loader tests against a synthetic fixture zip (04 §10)."""

import zipfile
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.conftest import requires_db

from rental_agent.contracts import enums as e
from rental_agent.db.models import TransitRoute, TransitStop
from rental_agent.enrichment.transit.gtfs_loader import ingest_dataset, parse_gtfs_zip

pytestmark = requires_db

ROUTES_TXT = """route_id,route_short_name,route_long_name,route_type
1,1,Broadway - 7 Avenue Local,1
A,A,8 Avenue Express,1
"""

STOPS_TXT = """stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station
127,Times Sq-42 St,40.75529,-73.987495,1,
127N,Times Sq-42 St,40.75529,-73.987495,0,127
127S,Times Sq-42 St,40.75529,-73.987495,0,127
NOCOORD,Ghost Stop,,,0,
"""


@pytest.fixture()
def gtfs_zip(tmp_path: Path) -> Path:
    path = tmp_path / "gtfs_subway.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("routes.txt", ROUTES_TXT)
        archive.writestr("stops.txt", STOPS_TXT)
    return path


def test_parse_maps_modes_and_skips_missing_coordinates(gtfs_zip: Path):
    dataset = parse_gtfs_zip(gtfs_zip, operator_code="MTA", dataset_version="test-1")
    assert {r.provider_route_id for r in dataset.routes} == {"1", "A"}
    assert all(r.mode is e.TransitMode.SUBWAY for r in dataset.routes)
    # Ghost stop without coordinates is never fabricated into existence.
    assert {s.provider_stop_id for s in dataset.stops} == {"127", "127N", "127S"}
    parent = next(s for s in dataset.stops if s.provider_stop_id == "127N")
    assert parent.parent_provider_stop_id == "127"


def test_mode_override_for_path(gtfs_zip: Path):
    dataset = parse_gtfs_zip(
        gtfs_zip,
        operator_code="PATH",
        dataset_version="test-1",
        mode_override=e.TransitMode.PATH,
    )
    assert all(r.mode is e.TransitMode.PATH for r in dataset.routes)
    assert all(s.mode is e.TransitMode.PATH for s in dataset.stops)


def test_ingest_is_idempotent_and_links_parents(db_session: Session, seeded_source, gtfs_zip: Path):
    dataset = parse_gtfs_zip(gtfs_zip, operator_code="MTA", dataset_version="test-1")
    counts = ingest_dataset(db_session, dataset, provider_source_id=seeded_source)
    db_session.commit()
    assert counts == {"stops_inserted": 3, "routes_inserted": 2, "parents_linked": 2}

    # Re-ingest: no duplicates, no new links.
    counts2 = ingest_dataset(db_session, dataset, provider_source_id=seeded_source)
    db_session.commit()
    assert counts2 == {"stops_inserted": 0, "routes_inserted": 0, "parents_linked": 0}
    assert db_session.execute(select(func.count()).select_from(TransitStop)).scalar() == 3
    assert db_session.execute(select(func.count()).select_from(TransitRoute)).scalar() == 2

    child = db_session.execute(
        select(TransitStop).where(TransitStop.provider_stop_id == "127N")
    ).scalar_one()
    parent = db_session.execute(
        select(TransitStop).where(TransitStop.provider_stop_id == "127")
    ).scalar_one()
    assert child.parent_stop_id == parent.transit_stop_id
    # Spatial data round-trips.
    from sqlalchemy import text

    lon = db_session.execute(
        text(
            "SELECT ST_X(location_point::geometry) FROM app.transit_stop "
            "WHERE provider_stop_id = '127'"
        )
    ).scalar_one()
    assert round(lon, 4) == -73.9875
