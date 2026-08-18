"""Test configuration.

Integration tests run against the real PostgreSQL/PostGIS ``rental_test``
database (never SQLite — 08 forbids concealing PostGIS behavior). At session
start the five app schemas are dropped and the Alembic baseline is applied to a
genuinely fresh database, which itself verifies fresh-setup reapplication.
"""

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

TEST_DB_URL = os.environ.get(
    "RENTAL_TEST_DB_URL",
    "postgresql+psycopg://rental:rental_local_dev@localhost:5433/rental_test",
)


def _db_available() -> bool:
    try:
        eng = create_engine(TEST_DB_URL, connect_args={"connect_timeout": 3})
        with eng.connect():
            return True
    except Exception:
        return False


DB_AVAILABLE = _db_available()

requires_db = pytest.mark.skipif(
    not DB_AVAILABLE, reason="rental_test PostgreSQL/PostGIS database not reachable"
)


@pytest.fixture(scope="session")
def migrated_engine() -> Iterator[Engine]:
    if not DB_AVAILABLE:
        pytest.skip("test database unavailable")
    from alembic import command
    from alembic.config import Config

    engine = create_engine(TEST_DB_URL)
    with engine.begin() as conn:
        for schema in ("app", "ops", "raw", "config", "audit"):
            conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS public.alembic_version"))

    os.environ["ALEMBIC_DB_URL"] = TEST_DB_URL
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")

    yield engine
    engine.dispose()


def _truncate_all(engine: Engine) -> None:
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT table_schema, table_name FROM information_schema.tables "
                "WHERE table_schema IN ('app','ops','raw','audit') AND table_type = 'BASE TABLE'"
            )
        ).all()
        if rows:
            names = ", ".join(f"{s}.{t}" for s, t in rows)
            conn.execute(text(f"TRUNCATE {names} CASCADE"))


@pytest.fixture()
def db_engine(migrated_engine: Engine) -> Iterator[Engine]:
    yield migrated_engine
    _truncate_all(migrated_engine)


@pytest.fixture()
def db_session(db_engine: Engine) -> Iterator[Session]:
    with Session(db_engine) as session:
        yield session
        session.rollback()


@pytest.fixture()
def seeded_source(db_session: Session) -> uuid.UUID:
    from rental_agent.db.models import Source

    source = Source(
        source_code=f"test_source_{uuid.uuid4().hex[:8]}",
        display_name="Test Source",
        source_type="LISTING",
        access_method="MANUAL_IMPORT",
        policy_version="test-0",
    )
    db_session.add(source)
    db_session.commit()
    return source.source_id


@pytest.fixture()
def seeded_listing(db_session: Session) -> uuid.UUID:
    """A minimal address -> building -> canonical listing chain."""
    from rental_agent.db.models import Address, Building, CanonicalListing

    now = datetime.now(tz=UTC)
    address = Address(
        locality="New York",
        administrative_area="NY",
        formatted_address="1 Test St, New York, NY",
    )
    db_session.add(address)
    db_session.flush()
    building = Building(address_id=address.address_id)
    db_session.add(building)
    db_session.flush()
    listing = CanonicalListing(
        building_id=building.building_id,
        first_seen_at=now,
        last_seen_at=now,
        last_material_change_at=now,
    )
    db_session.add(listing)
    db_session.commit()
    return listing.canonical_listing_id
