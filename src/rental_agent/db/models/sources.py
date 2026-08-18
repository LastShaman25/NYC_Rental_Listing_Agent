"""Source registry, refresh runs, source runs, and raw source observations.

Spec: 02 §6, 06 §6.1–6.2. Adapters write observations only; canonical mutation
belongs to downstream normalization/identity resolution (03 §7.1).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from rental_agent.contracts import enums as e
from rental_agent.db.base import Base, created_at, enum_text, updated_at, uuid_pk


class Source(Base):
    __tablename__ = "source"
    __table_args__ = ({"schema": "app"},)

    source_id: Mapped[uuid.UUID] = uuid_pk()
    source_code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = enum_text(e.SourceType, "source_type", nullable=False)
    base_domain: Mapped[str | None]
    access_method: Mapped[str] = enum_text(e.AccessMethod, "access_method", nullable=False)
    approval_status: Mapped[str] = enum_text(
        e.SourceApprovalStatus,
        "approval_status",
        nullable=False,
        server_default=e.SourceApprovalStatus.PROPOSED.value,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    policy_version: Mapped[str] = mapped_column(Text, nullable=False)
    configuration: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # non-secret only
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class RefreshRun(Base):
    __tablename__ = "refresh_run"
    __table_args__ = ({"schema": "ops"},)

    refresh_run_id: Mapped[uuid.UUID] = uuid_pk()
    trigger_type: Mapped[str] = enum_text(e.RefreshTriggerType, "trigger_type", nullable=False)
    # Duplicate scheduler triggers must join the existing logical run (06 §9.4).
    logical_run_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    scheduled_for: Mapped[datetime | None]
    started_at: Mapped[datetime] = mapped_column(nullable=False)
    completed_at: Mapped[datetime | None]
    status: Mapped[str] = enum_text(
        e.RefreshRunStatus,
        "status",
        nullable=False,
        server_default=e.RefreshRunStatus.PENDING.value,
    )
    pipeline_version: Mapped[str] = mapped_column(Text, nullable=False)
    summary_counts: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = created_at()


class SourceRun(Base):
    __tablename__ = "source_run"
    __table_args__ = (
        UniqueConstraint("refresh_run_id", "source_id"),
        {"schema": "ops"},
    )

    source_run_id: Mapped[uuid.UUID] = uuid_pk()
    refresh_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.refresh_run.refresh_run_id"), nullable=False
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.source.source_id"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(nullable=False)
    completed_at: Mapped[datetime | None]
    status: Mapped[str] = enum_text(
        e.SourceRunStatus, "status", nullable=False, server_default=e.SourceRunStatus.PENDING.value
    )
    health_gate_passed: Mapped[bool | None] = mapped_column(Boolean)  # null until evaluated
    expected_scope: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    counts: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    adapter_version: Mapped[str] = mapped_column(Text, nullable=False)


class SourceObservation(Base):
    __tablename__ = "source_observation"
    __table_args__ = (
        # Idempotency (02 §6.4): native-ID key when present, URL-based otherwise.
        Index(
            "uq_source_observation_native_identity",
            "source_id",
            "source_native_id",
            "content_hash",
            "observed_at",
            unique=True,
            postgresql_where=text("source_native_id IS NOT NULL"),
        ),
        Index(
            "uq_source_observation_url_identity",
            "source_id",
            "source_url",
            "content_hash",
            "observed_at",
            unique=True,
            postgresql_where=text("source_native_id IS NULL"),
        ),
        Index(
            "ix_source_observation_source_native_observed",
            "source_id",
            "source_native_id",
            text("observed_at DESC"),
        ),
        {"schema": "raw"},
    )

    source_observation_id: Mapped[uuid.UUID] = uuid_pk()
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.source.source_id"), nullable=False
    )
    source_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.source_run.source_run_id"), nullable=False
    )
    source_native_id: Mapped[str | None]
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    raw_payload_ref: Mapped[str | None]  # relative path under local_data/raw
    parsed_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    parse_status: Mapped[str] = enum_text(e.ParseStatus, "parse_status", nullable=False)
    validation_issues: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    contact_redaction_status: Mapped[str] = enum_text(
        e.ContactRedactionStatus, "contact_redaction_status", nullable=False
    )
    adapter_version: Mapped[str] = mapped_column(Text, nullable=False)
    schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    recorded_at: Mapped[datetime] = created_at()


class AdapterCheckpoint(Base):
    """Resumable acquisition checkpoints (03 §9.3, 06 §6.2)."""

    __tablename__ = "adapter_checkpoint"
    __table_args__ = (
        UniqueConstraint("source_run_id", "partition_key"),
        {"schema": "ops"},
    )

    adapter_checkpoint_id: Mapped[uuid.UUID] = uuid_pk()
    source_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.source_run.source_run_id"), nullable=False
    )
    partition_key: Mapped[str] = mapped_column(Text, nullable=False)
    cursor_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    items_discovered: Mapped[int | None] = mapped_column(BigInteger)
    updated_at: Mapped[datetime] = updated_at()
