from sqlalchemy import select, text
from sqlalchemy.orm import Session
from tests.conftest import requires_db

from rental_agent.config.destination_seed import ALL_DESTINATIONS, seed_destinations
from rental_agent.db.models import Destination

pytestmark = requires_db


def test_seed_contains_all_required_registry_entries():
    codes = {d.code for d in ALL_DESTINATIONS}
    # PR-COMMUTE-003/004: separate campuses, separate Fordham/NYU anchors.
    assert {"NYU_WASHINGTON_SQUARE", "NYU_TANDON"} <= codes
    assert {"FORDHAM_ROSE_HILL", "FORDHAM_LINCOLN_CENTER"} <= codes
    assert len(codes) == 20


def test_seed_is_idempotent_and_spatially_valid(db_session: Session):
    assert seed_destinations(db_session) == 20
    db_session.commit()
    assert seed_destinations(db_session) == 0  # reseed adds nothing

    rows = db_session.execute(select(Destination)).scalars().all()
    assert len(rows) == 20
    assert all(d.registry_version == "v1-reviewed-2026-08-17" for d in rows)

    # Anchors are genuinely distinct points in the NYC/NJ area.
    distinct = db_session.execute(
        text(
            "SELECT count(DISTINCT ST_AsText(routing_anchor_point::geometry)) FROM app.destination"
        )
    ).scalar_one()
    assert distinct == 20
    bounds_ok = db_session.execute(
        text(
            "SELECT bool_and(ST_X(routing_anchor_point::geometry) BETWEEN -74.3 AND -73.7 "
            "AND ST_Y(routing_anchor_point::geometry) BETWEEN 40.5 AND 41.0) FROM app.destination"
        )
    ).scalar_one()
    assert bounds_ok is True
