"""Provider requests, model executions, and the PostgreSQL-backed leased job queue.

Spec: 02 §11, §16.2, §20; 06 §12 (claiming, leases, heartbeats, priorities).
Windows Task Scheduler owns recurring scheduling; nothing here self-schedules.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from rental_agent.contracts import enums as e
from rental_agent.db.base import Base, created_at, enum_text, updated_at, uuid_pk


class ProviderRequest(Base):
    __tablename__ = "provider_request"
    __table_args__ = (
        UniqueConstraint("source_id", "request_type", "request_hash"),
        {"schema": "ops"},
    )

    provider_request_id: Mapped[uuid.UUID] = uuid_pk()
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.source.source_id"), nullable=False
    )
    request_type: Mapped[str] = enum_text(e.ProviderRequestType, "request_type", nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    request_parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    provider_result_id: Mapped[str | None]
    response_ref: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = enum_text(
        e.ProviderRequestStatus,
        "status",
        nullable=False,
        server_default=e.ProviderRequestStatus.PENDING.value,
    )
    requested_at: Mapped[datetime] = mapped_column(nullable=False)
    completed_at: Mapped[datetime | None]
    expires_at: Mapped[datetime | None]
    error_code: Mapped[str | None]


class ModelExecution(Base):
    __tablename__ = "model_execution"
    __table_args__ = (
        # Cache uniqueness (02 §11.1).
        UniqueConstraint(
            "task_type", "input_hash", "prompt_version", "output_schema_version", "model_id"
        ),
        {"schema": "ops"},
    )

    model_execution_id: Mapped[uuid.UUID] = uuid_pk()
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.job.job_id")
    )
    provider_code: Mapped[str] = mapped_column(Text, nullable=False)
    model_id: Mapped[str] = mapped_column(Text, nullable=False)
    model_tier: Mapped[str] = enum_text(e.ModelTier, "model_tier", nullable=False)
    task_type: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    output_schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    input_hash: Mapped[str] = mapped_column(Text, nullable=False)
    input_refs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    output_ref: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    confidence: Mapped[str] = enum_text(
        e.Confidence, "confidence", nullable=False, server_default=e.Confidence.UNKNOWN.value
    )
    validation_status: Mapped[str] = enum_text(
        e.ValidationStatus,
        "validation_status",
        nullable=False,
        server_default=e.ValidationStatus.PENDING.value,
    )
    escalated_from_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.model_execution.model_execution_id")
    )
    input_tokens: Mapped[int | None] = mapped_column(BigInteger)
    output_tokens: Mapped[int | None] = mapped_column(BigInteger)
    cost_minor: Mapped[int | None] = mapped_column(BigInteger)
    currency_code: Mapped[str | None]
    started_at: Mapped[datetime] = mapped_column(nullable=False)
    completed_at: Mapped[datetime | None]
    status: Mapped[str] = enum_text(
        e.ModelExecutionStatus,
        "status",
        nullable=False,
        server_default=e.ModelExecutionStatus.PENDING.value,
    )


class Job(Base):
    __tablename__ = "job"
    __table_args__ = (
        # Idempotency for live jobs (02 §20.1): terminal-failed/cancelled rows do
        # not block re-enqueueing.
        Index(
            "uq_job_active_identity",
            "job_type",
            "canonical_listing_id",
            "input_hash",
            "dependency_version",
            unique=True,
            postgresql_nulls_not_distinct=True,
            postgresql_where=text("status NOT IN ('FAILED_TERMINAL', 'CANCELLED')"),
        ),
        # Claim path (06 §7.3): claimable jobs by priority/time.
        Index(
            "ix_job_claimable",
            "status",
            text("priority DESC"),
            "next_attempt_at",
            postgresql_where=text("status IN ('PENDING', 'FAILED_RETRYABLE')"),
        ),
        Index("ix_job_listing_type", "canonical_listing_id", "job_type"),
        {"schema": "ops"},
    )

    job_id: Mapped[uuid.UUID] = uuid_pk()
    refresh_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.refresh_run.refresh_run_id")
    )
    canonical_listing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.canonical_listing.canonical_listing_id")
    )
    job_type: Mapped[str] = enum_text(e.JobType, "job_type", nullable=False)
    input_hash: Mapped[str] = mapped_column(Text, nullable=False)
    dependency_version: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = enum_text(
        e.JobStatus, "status", nullable=False, server_default=e.JobStatus.PENDING.value
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("3"))
    next_attempt_at: Mapped[datetime | None]
    started_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]
    error_code: Mapped[str | None]
    error_detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # Lease fields (06 §12.2)
    lease_token: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    leased_by: Mapped[str | None]
    lease_expires_at: Mapped[datetime | None]
    heartbeat_at: Mapped[datetime | None]
    cancellation_requested_at: Mapped[datetime | None]
    terminal_reason: Mapped[str | None]
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class JobAttempt(Base):
    __tablename__ = "job_attempt"
    __table_args__ = (
        UniqueConstraint("job_id", "attempt_number"),
        {"schema": "ops"},
    )

    job_attempt_id: Mapped[uuid.UUID] = uuid_pk()
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.job.job_id"), nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    lease_token: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    leased_by: Mapped[str | None]
    started_at: Mapped[datetime] = mapped_column(nullable=False)
    completed_at: Mapped[datetime | None]
    outcome_status: Mapped[str | None]
    error_code: Mapped[str | None]
    error_detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class JobDependency(Base):
    __tablename__ = "job_dependency"
    __table_args__ = (
        UniqueConstraint("job_id", "depends_on_job_id"),
        {"schema": "ops"},
    )

    job_dependency_id: Mapped[uuid.UUID] = uuid_pk()
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.job.job_id"), nullable=False
    )
    depends_on_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.job.job_id"), nullable=False
    )
