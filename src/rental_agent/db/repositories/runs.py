"""Refresh-run and source-run persistence (06 §9–10).

Run creation is idempotent on the logical run key so a duplicate scheduler
trigger joins the existing run instead of creating a second one (06 §9.4).
Recurring scheduling itself belongs to Windows Task Scheduler, never here.
"""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from rental_agent.contracts import enums as e
from rental_agent.db.models import RefreshRun, SourceRun


class RefreshRunRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def create_or_join(
        self,
        *,
        logical_run_key: str,
        trigger_type: e.RefreshTriggerType,
        started_at: datetime,
        pipeline_version: str,
        scheduled_for: datetime | None = None,
    ) -> tuple[uuid.UUID, bool]:
        """Returns (refresh_run_id, created). Duplicate keys join the existing run."""
        stmt = (
            pg_insert(RefreshRun)
            .values(
                logical_run_key=logical_run_key,
                trigger_type=trigger_type.value,
                started_at=started_at,
                scheduled_for=scheduled_for,
                status=e.RefreshRunStatus.PENDING.value,
                pipeline_version=pipeline_version,
            )
            .on_conflict_do_nothing(index_elements=["logical_run_key"])
            .returning(RefreshRun.refresh_run_id)
        )
        run_id = self._s.execute(stmt).scalar_one_or_none()
        if run_id is not None:
            return run_id, True
        existing = self._s.execute(
            select(RefreshRun.refresh_run_id).where(RefreshRun.logical_run_key == logical_run_key)
        ).scalar_one()
        return existing, False

    def set_status(
        self,
        refresh_run_id: uuid.UUID,
        status: e.RefreshRunStatus,
        completed_at: datetime | None = None,
        summary_counts: dict | None = None,
    ) -> None:
        run = self._s.get(RefreshRun, refresh_run_id)
        if run is None:
            raise LookupError(f"refresh run {refresh_run_id} not found")
        run.status = status.value
        if completed_at is not None:
            run.completed_at = completed_at
        if summary_counts is not None:
            run.summary_counts = summary_counts

    def create_source_run(
        self,
        *,
        refresh_run_id: uuid.UUID,
        source_id: uuid.UUID,
        started_at: datetime,
        adapter_version: str,
    ) -> uuid.UUID:
        row = SourceRun(
            refresh_run_id=refresh_run_id,
            source_id=source_id,
            started_at=started_at,
            adapter_version=adapter_version,
        )
        self._s.add(row)
        self._s.flush()
        return row.source_run_id
