"""Repository behaviors: idempotent observation insert, run join semantics, source seed."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.conftest import requires_db

from rental_agent.contracts.enums import ParseStatus, RefreshTriggerType
from rental_agent.contracts.fakes import minimal_observation
from rental_agent.db.models import Source, SourceObservation
from rental_agent.db.repositories.observations import ObservationRepository
from rental_agent.db.repositories.runs import RefreshRunRepository

pytestmark = requires_db

NOW = datetime.now(tz=UTC)


def _source_run(db_session: Session, source_id: uuid.UUID) -> uuid.UUID:
    runs = RefreshRunRepository(db_session)
    run_id, _ = runs.create_or_join(
        logical_run_key=f"test:{uuid.uuid4().hex}",
        trigger_type=RefreshTriggerType.MANUAL,
        started_at=NOW,
        pipeline_version="t1",
    )
    return runs.create_source_run(
        refresh_run_id=run_id, source_id=source_id, started_at=NOW, adapter_version="t1"
    )


def test_observation_insert_is_idempotent(db_session: Session, seeded_source):
    source_run_id = _source_run(db_session, seeded_source)
    repo = ObservationRepository(db_session)
    obs = minimal_observation(observed_at=NOW)

    first = repo.insert_idempotent(
        obs,
        source_id=seeded_source,
        source_run_id=source_run_id,
        content_hash="h1",
        parse_status=ParseStatus.VALID,
    )
    second = repo.insert_idempotent(
        obs,
        source_id=seeded_source,
        source_run_id=source_run_id,
        content_hash="h1",
        parse_status=ParseStatus.VALID,
    )
    db_session.commit()
    assert first is not None
    assert second is None  # replay created no duplicate observation
    count = db_session.execute(select(func.count()).select_from(SourceObservation)).scalar()
    assert count == 1


def test_changed_content_creates_new_observation(db_session: Session, seeded_source):
    source_run_id = _source_run(db_session, seeded_source)
    repo = ObservationRepository(db_session)
    obs = minimal_observation(observed_at=NOW)
    a = repo.insert_idempotent(
        obs,
        source_id=seeded_source,
        source_run_id=source_run_id,
        content_hash="h1",
        parse_status=ParseStatus.VALID,
    )
    b = repo.insert_idempotent(
        obs,
        source_id=seeded_source,
        source_run_id=source_run_id,
        content_hash="h2",  # material content change -> distinct observation
        parse_status=ParseStatus.VALID,
    )
    db_session.commit()
    assert a is not None and b is not None and a != b


def test_duplicate_scheduled_trigger_joins_existing_run(db_session: Session):
    runs = RefreshRunRepository(db_session)
    key = "weekday_inventory_refresh:2026-08-17:v1"
    first_id, created_first = runs.create_or_join(
        logical_run_key=key,
        trigger_type=RefreshTriggerType.SCHEDULED,
        started_at=NOW,
        pipeline_version="t1",
    )
    db_session.commit()
    second_id, created_second = runs.create_or_join(
        logical_run_key=key,
        trigger_type=RefreshTriggerType.SCHEDULED,
        started_at=NOW,
        pipeline_version="t1",
    )
    db_session.commit()
    assert created_first is True
    assert created_second is False
    assert first_id == second_id


def test_source_seed_is_disabled_and_proposed(db_session: Session):
    from rental_agent.config.source_seed import seed_sources

    added = seed_sources(db_session)
    db_session.commit()
    assert added > 0
    listing_sources = (
        db_session.execute(select(Source).where(Source.source_type == "LISTING")).scalars().all()
    )
    assert listing_sources
    for source in listing_sources:
        assert source.enabled is False
        assert source.approval_status == "PROPOSED"
    # Idempotent reseed adds nothing.
    assert seed_sources(db_session) == 0
