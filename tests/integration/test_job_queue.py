"""Leased job-queue semantics (06 §12; acceptance tests 3, 4)."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import update
from sqlalchemy.orm import Session
from tests.conftest import requires_db

from rental_agent.contracts.enums import JobStatus, JobType
from rental_agent.db.models import Job
from rental_agent.jobs.queue import JobQueue

pytestmark = requires_db


def _enqueue(session: Session, **kw) -> uuid.UUID:
    queue = JobQueue(session)
    job_id = queue.enqueue(
        job_type=kw.pop("job_type", JobType.NORMALIZE),
        input_hash=kw.pop("input_hash", uuid.uuid4().hex),
        dependency_version="v1",
        **kw,
    )
    session.commit()
    assert job_id is not None
    return job_id


def test_enqueue_is_idempotent(db_session: Session):
    queue = JobQueue(db_session)
    first = queue.enqueue(job_type=JobType.GEOCODE, input_hash="same", dependency_version="v1")
    second = queue.enqueue(job_type=JobType.GEOCODE, input_hash="same", dependency_version="v1")
    db_session.commit()
    assert first is not None
    assert second is None  # duplicate live job suppressed


def test_terminal_job_does_not_block_reenqueue(db_session: Session):
    queue = JobQueue(db_session)
    first = queue.enqueue(job_type=JobType.GEOCODE, input_hash="k", dependency_version="v1")
    db_session.commit()
    [job] = queue.claim(worker_id="w1")
    token = job.lease_token
    queue.complete(job.job_id, token, status=JobStatus.FAILED_TERMINAL)
    db_session.commit()
    again = queue.enqueue(job_type=JobType.GEOCODE, input_hash="k", dependency_version="v1")
    db_session.commit()
    assert first is not None and again is not None


def test_concurrent_claim_exclusivity(db_engine):
    """Two workers on separate connections never claim the same job."""
    with Session(db_engine) as s0:
        job_id = _enqueue(s0)

    session_a = Session(db_engine)
    session_b = Session(db_engine)
    try:
        claimed_a = JobQueue(session_a).claim(worker_id="worker-a")
        # A holds the row lock; B must skip it rather than block or double-claim.
        claimed_b = JobQueue(session_b).claim(worker_id="worker-b")
        assert [j.job_id for j in claimed_a] == [job_id]
        assert claimed_b == []
        session_a.commit()
        # After A commits, the job is RUNNING and still unclaimable.
        session_b.rollback()
        assert JobQueue(session_b).claim(worker_id="worker-b") == []
    finally:
        session_a.close()
        session_b.close()


def test_completion_requires_current_lease(db_session: Session):
    _enqueue(db_session)
    queue = JobQueue(db_session)
    [job] = queue.claim(worker_id="w1")
    db_session.commit()
    wrong_token = uuid.uuid4()
    assert queue.complete(job.job_id, wrong_token, status=JobStatus.SUCCEEDED) is False
    assert queue.complete(job.job_id, job.lease_token, status=JobStatus.SUCCEEDED) is True
    db_session.commit()


def test_expired_lease_recovery(db_session: Session):
    job_id = _enqueue(db_session)
    queue = JobQueue(db_session)
    [job] = queue.claim(worker_id="w1")
    db_session.commit()
    # Simulate a crashed worker: force the lease into the past.
    db_session.execute(
        update(Job)
        .where(Job.job_id == job_id)
        .values(lease_expires_at=datetime.now(tz=UTC) - timedelta(seconds=1))
    )
    db_session.commit()
    recovered = queue.recover_expired_leases()
    db_session.commit()
    assert recovered == 1
    [reclaimed] = queue.claim(worker_id="w2")
    assert reclaimed.job_id == job_id
    assert reclaimed.attempt_count == 2
    db_session.commit()


def test_retry_exhaustion_becomes_terminal(db_session: Session):
    _enqueue(db_session, max_attempts=1)
    queue = JobQueue(db_session)
    [job] = queue.claim(worker_id="w1")
    queue.complete(job.job_id, job.lease_token, status=JobStatus.FAILED_RETRYABLE)
    db_session.commit()
    refreshed = db_session.get(Job, job.job_id)
    assert refreshed.status == JobStatus.FAILED_TERMINAL.value
    assert refreshed.terminal_reason == "max_attempts_exhausted"
