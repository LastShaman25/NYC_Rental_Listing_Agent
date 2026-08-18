"""Acquisition runner: one source's participation in a refresh (03 §9, 06 §11).

Orchestrates adapter preflight → partition planning → checkpointed discovery →
capture/extract/validate → idempotent observation persistence → NORMALIZE job
enqueueing → source-health evaluation. The runner never mutates canonical
lifecycle state; normalization happens through queued jobs processed by
``drain_normalize_jobs`` (worker path), keeping page/UI, orchestration, and
canonical rules separated.

Search-index sources (B3): ``health_gate_passed`` is always False — search
absence is never disappearance evidence (03 §5.4.5), regardless of how healthy
the discovery run itself was.
"""

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from rental_agent.canonical.normalization import NormalizationService
from rental_agent.config.logging import get_logger
from rental_agent.contracts import enums as e
from rental_agent.contracts.providers import SourceAdapter
from rental_agent.db.models import AdapterCheckpoint, Job, Source, SourceRun
from rental_agent.db.repositories.observations import ObservationRepository
from rental_agent.db.repositories.runs import RefreshRunRepository
from rental_agent.jobs.queue import JobQueue

log = get_logger(__name__)

PIPELINE_VERSION = "0.2.0"
NORMALIZE_DEPENDENCY_VERSION = "phase3-skeleton-1"


@dataclass
class SourceRunSummary:
    source_run_id: uuid.UUID
    status: e.SourceRunStatus
    health_gate_passed: bool
    discovered: int = 0
    persisted_new: int = 0
    duplicates_skipped: int = 0
    partitions_completed: int = 0
    partitions_failed: int = 0
    normalize_jobs_enqueued: int = 0
    errors: list[str] = field(default_factory=list)


class AcquisitionRunner:
    """Runs one adapter inside one refresh run. Sessions are short-lived; no
    transaction stays open across adapter/network calls (06 §13.3)."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._factory = session_factory

    def run_source(
        self,
        adapter: SourceAdapter,
        *,
        logical_run_key: str,
        trigger_type: e.RefreshTriggerType,
        discovery_method: e.DiscoveryMethod,
    ) -> SourceRunSummary:
        now = datetime.now(tz=UTC)

        # Transaction 1: run bookkeeping.
        with self._factory() as session:
            source = session.execute(
                select(Source).where(Source.source_code == adapter.source_code)
            ).scalar_one_or_none()
            if source is None:
                raise LookupError(f"source '{adapter.source_code}' not registered")
            runs = RefreshRunRepository(session)
            refresh_run_id, _ = runs.create_or_join(
                logical_run_key=logical_run_key,
                trigger_type=trigger_type,
                started_at=now,
                pipeline_version=PIPELINE_VERSION,
            )
            existing = session.execute(
                select(SourceRun).where(
                    SourceRun.refresh_run_id == refresh_run_id,
                    SourceRun.source_id == source.source_id,
                )
            ).scalar_one_or_none()
            source_run_id = (
                existing.source_run_id
                if existing is not None
                else runs.create_source_run(
                    refresh_run_id=refresh_run_id,
                    source_id=source.source_id,
                    started_at=now,
                    adapter_version=adapter.adapter_version,
                )
            )
            source_id = source.source_id
            session.commit()

        summary = SourceRunSummary(
            source_run_id=source_run_id,
            status=e.SourceRunStatus.RUNNING,
            health_gate_passed=False,
        )

        # Preflight happens outside any transaction.
        preflight = adapter.preflight({})
        if preflight.result == "BLOCKED":
            summary.status = e.SourceRunStatus.BLOCKED
            summary.errors.extend(preflight.reasons)
            self._finalize(source_run_id, summary, discovery_method)
            return summary

        degraded = preflight.result == "DEGRADED"

        # Intra-source dedup across overlapping partitions (03 §20): one
        # discovered identity is captured at most once per source run.
        seen_identities: set[str] = set()

        for partition in adapter.plan_partitions({}):
            try:
                partition_degraded = self._run_partition(
                    adapter,
                    partition,
                    source_id,
                    source_run_id,
                    refresh_run_id,
                    summary,
                    seen_identities,
                )
                degraded = degraded or partition_degraded
                summary.partitions_completed += 1
            except Exception as exc:  # noqa: BLE001 - partition isolation (03 §3.8)
                summary.partitions_failed += 1
                summary.errors.append(f"{partition.partition_key}: {type(exc).__name__}")
                log.error(
                    "partition_failed",
                    partition=partition.partition_key,
                    source_run_id=str(source_run_id),
                    error=type(exc).__name__,
                )

        if summary.partitions_failed and summary.partitions_completed == 0:
            summary.status = e.SourceRunStatus.FAILED
        elif summary.partitions_failed or degraded:
            summary.status = e.SourceRunStatus.DEGRADED
        else:
            summary.status = e.SourceRunStatus.HEALTHY

        # B3: search-discovered scope can never pass the disappearance gate.
        summary.health_gate_passed = (
            summary.status is e.SourceRunStatus.HEALTHY
            and discovery_method is not e.DiscoveryMethod.SEARCH_INDEX
        )
        self._finalize(source_run_id, summary, discovery_method)
        return summary

    def _run_partition(
        self,
        adapter: SourceAdapter,
        partition,
        source_id: uuid.UUID,
        source_run_id: uuid.UUID,
        refresh_run_id: uuid.UUID,
        summary: SourceRunSummary,
        seen_identities: set[str],
    ) -> bool:
        """Returns True when the partition looks degraded (truncated/errored)."""
        with self._factory() as session:
            checkpoint = session.execute(
                select(AdapterCheckpoint).where(
                    AdapterCheckpoint.source_run_id == source_run_id,
                    AdapterCheckpoint.partition_key == partition.partition_key,
                )
            ).scalar_one_or_none()
            if checkpoint is not None and checkpoint.completed:
                return False  # replay: partition already done
            session.commit()

        page = adapter.discover(partition, None)  # network: outside transactions
        degraded = bool(page.appears_truncated or page.health_markers.get("search_error"))
        summary.discovered += len(page.items)

        for item in page.items:
            identity = item.source_native_id or item.detail_url
            if identity in seen_identities:
                summary.duplicates_skipped += 1
                continue
            seen_identities.add(identity)
            capture = adapter.fetch_detail(item)
            observation = adapter.extract(capture)
            content_hash = (
                capture.content_hash
                or hashlib.sha256(observation.model_dump_json().encode()).hexdigest()
            )

            with self._factory() as session:
                obs_id = ObservationRepository(session).insert_idempotent(
                    observation,
                    source_id=source_id,
                    source_run_id=source_run_id,
                    content_hash=content_hash,
                    parse_status=observation.validation.parse_status,
                )
                if obs_id is None:
                    summary.duplicates_skipped += 1
                else:
                    summary.persisted_new += 1
                    job_id = JobQueue(session).enqueue(
                        job_type=e.JobType.NORMALIZE,
                        input_hash=str(obs_id),
                        dependency_version=NORMALIZE_DEPENDENCY_VERSION,
                        refresh_run_id=refresh_run_id,
                        priority=10,
                    )
                    if job_id is not None:
                        summary.normalize_jobs_enqueued += 1
                session.commit()

        with self._factory() as session:
            checkpoint = session.execute(
                select(AdapterCheckpoint).where(
                    AdapterCheckpoint.source_run_id == source_run_id,
                    AdapterCheckpoint.partition_key == partition.partition_key,
                )
            ).scalar_one_or_none()
            if checkpoint is None:
                checkpoint = AdapterCheckpoint(
                    source_run_id=source_run_id, partition_key=partition.partition_key
                )
                session.add(checkpoint)
            checkpoint.completed = True
            checkpoint.items_discovered = len(page.items)
            session.commit()
        return degraded

    def _finalize(
        self,
        source_run_id: uuid.UUID,
        summary: SourceRunSummary,
        discovery_method: e.DiscoveryMethod,
    ) -> None:
        with self._factory() as session:
            row = session.get(SourceRun, source_run_id)
            assert row is not None
            row.status = summary.status.value
            row.completed_at = datetime.now(tz=UTC)
            row.health_gate_passed = summary.health_gate_passed
            row.counts = {
                "discovered": summary.discovered,
                "persisted_new": summary.persisted_new,
                "duplicates_skipped": summary.duplicates_skipped,
                "partitions_completed": summary.partitions_completed,
                "partitions_failed": summary.partitions_failed,
                "normalize_jobs_enqueued": summary.normalize_jobs_enqueued,
                "discovery_method": discovery_method.value,
            }
            if summary.errors:
                row.error_summary = {"errors": summary.errors[:50]}
            session.commit()


def drain_normalize_jobs(
    session_factory: sessionmaker[Session],
    *,
    worker_id: str = "normalize-worker",
    discovery_method: e.DiscoveryMethod,
    max_jobs: int = 1000,
) -> int:
    """Worker loop: claim and process queued NORMALIZE jobs. Each job's claim,
    work, and completion commit independently so a failure isolates to one job."""
    processed = 0
    while processed < max_jobs:
        with session_factory() as session:
            queue = JobQueue(session)
            claimed = queue.claim(worker_id=worker_id, batch_size=1)
            claimed = [j for j in claimed if j.job_type == e.JobType.NORMALIZE.value]
            if not claimed:
                session.commit()
                break
            job: Job = claimed[0]
            job_id = job.job_id
            lease = job.lease_token
            assert lease is not None  # claim() always sets a lease token
            observation_id = uuid.UUID(job.input_hash)
            session.commit()

        with session_factory() as session:
            queue = JobQueue(session)
            try:
                NormalizationService(session).process_observation(
                    observation_id, discovery_method=discovery_method
                )
                queue.complete(job_id, lease, status=e.JobStatus.SUCCEEDED)
                session.commit()
            except Exception as exc:  # noqa: BLE001 - job isolation
                session.rollback()
                queue.complete(
                    job_id,
                    lease,
                    status=e.JobStatus.FAILED_RETRYABLE,
                    error_code=type(exc).__name__,
                )
                session.commit()
        processed += 1
    return processed
