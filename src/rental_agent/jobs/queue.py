"""PostgreSQL-backed leased job queue (06 §12).

Claiming uses FOR UPDATE SKIP LOCKED; completion and heartbeat require the
current lease token; expired leases return jobs to a claimable state within
attempt limits. Long-running external calls happen outside any open database
transaction — workers claim, commit, work, then report in a new transaction.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from rental_agent.contracts import enums as e
from rental_agent.db.models import Job, JobAttempt

CLAIMABLE_STATUSES = (e.JobStatus.PENDING.value, e.JobStatus.FAILED_RETRYABLE.value)


def _now() -> datetime:
    return datetime.now(tz=UTC)


class JobQueue:
    def __init__(self, session: Session) -> None:
        self._s = session

    def enqueue(
        self,
        *,
        job_type: e.JobType,
        input_hash: str,
        dependency_version: str,
        canonical_listing_id: uuid.UUID | None = None,
        refresh_run_id: uuid.UUID | None = None,
        priority: int = 0,
        max_attempts: int = 3,
        next_attempt_at: datetime | None = None,
    ) -> uuid.UUID | None:
        """Idempotent enqueue; returns job id or None when an equivalent live
        job already exists (02 §20.1)."""
        stmt = (
            pg_insert(Job)
            .values(
                job_type=job_type.value,
                input_hash=input_hash,
                dependency_version=dependency_version,
                canonical_listing_id=canonical_listing_id,
                refresh_run_id=refresh_run_id,
                priority=priority,
                max_attempts=max_attempts,
                next_attempt_at=next_attempt_at or _now(),
                status=e.JobStatus.PENDING.value,
            )
            .on_conflict_do_nothing()
            .returning(Job.job_id)
        )
        return self._s.execute(stmt).scalar_one_or_none()

    def claim(self, *, worker_id: str, lease_seconds: int = 300, batch_size: int = 1) -> list[Job]:
        """Claim up to batch_size jobs; lease and attempt row are written in the
        caller's transaction (06 §12.1)."""
        now = _now()
        candidate_ids = (
            self._s.execute(
                select(Job.job_id)
                .where(
                    Job.status.in_(CLAIMABLE_STATUSES),
                    Job.next_attempt_at <= now,
                    (Job.lease_expires_at.is_(None)) | (Job.lease_expires_at < now),
                    Job.attempt_count < Job.max_attempts,
                )
                .order_by(Job.priority.desc(), Job.created_at.asc())
                .with_for_update(skip_locked=True)
                .limit(batch_size)
            )
            .scalars()
            .all()
        )
        claimed: list[Job] = []
        for job_id in candidate_ids:
            job = self._s.get(Job, job_id)
            assert job is not None
            job.status = e.JobStatus.RUNNING.value
            job.lease_token = uuid.uuid4()
            job.leased_by = worker_id
            job.lease_expires_at = now + timedelta(seconds=lease_seconds)
            job.heartbeat_at = now
            job.attempt_count += 1
            job.started_at = now
            self._s.add(
                JobAttempt(
                    job_id=job.job_id,
                    attempt_number=job.attempt_count,
                    lease_token=job.lease_token,
                    leased_by=worker_id,
                    started_at=now,
                )
            )
            claimed.append(job)
        return claimed

    def heartbeat(
        self, job_id: uuid.UUID, lease_token: uuid.UUID, extend_seconds: int = 300
    ) -> bool:
        now = _now()
        cursor = self._s.execute(
            update(Job)
            .where(
                Job.job_id == job_id,
                Job.lease_token == lease_token,
                Job.status == e.JobStatus.RUNNING.value,
            )
            .values(heartbeat_at=now, lease_expires_at=now + timedelta(seconds=extend_seconds))
        )
        return cursor.rowcount == 1  # type: ignore[attr-defined]

    def complete(
        self,
        job_id: uuid.UUID,
        lease_token: uuid.UUID,
        *,
        status: e.JobStatus,
        error_code: str | None = None,
        error_detail: dict[str, Any] | None = None,
        retry_delay_seconds: int = 60,
    ) -> bool:
        """Terminal or retry transition; requires the current lease (06 §12.3)."""
        if status not in (
            e.JobStatus.SUCCEEDED,
            e.JobStatus.FAILED_RETRYABLE,
            e.JobStatus.FAILED_TERMINAL,
            e.JobStatus.CANCELLED,
            e.JobStatus.BLOCKED,
            e.JobStatus.CACHED,
        ):
            raise ValueError(f"not a completion status: {status}")
        now = _now()
        job = self._s.execute(
            select(Job)
            .where(Job.job_id == job_id, Job.lease_token == lease_token)
            .with_for_update()
        ).scalar_one_or_none()
        if job is None:
            return False
        if status is e.JobStatus.FAILED_RETRYABLE and job.attempt_count >= job.max_attempts:
            status = e.JobStatus.FAILED_TERMINAL
            job.terminal_reason = "max_attempts_exhausted"
        job.status = status.value
        job.error_code = error_code
        job.error_detail = error_detail
        job.lease_token = None
        job.leased_by = None
        job.lease_expires_at = None
        if status is e.JobStatus.FAILED_RETRYABLE:
            job.next_attempt_at = now + timedelta(seconds=retry_delay_seconds)
        else:
            job.completed_at = now
        attempt = self._s.execute(
            select(JobAttempt).where(
                JobAttempt.job_id == job_id, JobAttempt.attempt_number == job.attempt_count
            )
        ).scalar_one_or_none()
        if attempt is not None:
            attempt.completed_at = now
            attempt.outcome_status = status.value
            attempt.error_code = error_code
        return True

    def recover_expired_leases(self) -> int:
        """Return expired RUNNING jobs to a claimable state (06 §12.3)."""
        now = _now()
        result = self._s.execute(
            update(Job)
            .where(
                Job.status == e.JobStatus.RUNNING.value,
                Job.lease_expires_at.is_not(None),
                Job.lease_expires_at < now,
            )
            .values(
                status=e.JobStatus.FAILED_RETRYABLE.value,
                lease_token=None,
                leased_by=None,
                lease_expires_at=None,
                error_code="LEASE_EXPIRED",
                next_attempt_at=now,
            )
        )
        return result.rowcount  # type: ignore[attr-defined]

    def queue_depth(self) -> int:
        return self._s.execute(
            select(text("count(*)")).select_from(Job).where(Job.status.in_(CLAIMABLE_STATUSES))
        ).scalar_one()
