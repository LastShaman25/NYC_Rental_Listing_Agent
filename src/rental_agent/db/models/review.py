"""Human overrides, review issues, marketing selection, client presets/shortlists, audit log.

Spec: 02 §18–19; 08 §16.3. Marketing selection and client-shortlist membership
are strictly independent states; neither may be written by automatic jobs. The
service layer enforces the human-actor requirement; tests verify it.
"""

import uuid
from datetime import datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import Boolean, ForeignKey, Index, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from rental_agent.contracts import enums as e
from rental_agent.db.base import Base, created_at, enum_text, updated_at, uuid_pk


class HumanOverride(Base):
    __tablename__ = "human_override"
    __table_args__ = (
        Index(
            "uq_human_override_active",
            "entity_type",
            "entity_id",
            "field_name",
            unique=True,
            postgresql_where=text("override_status = 'ACTIVE'"),
        ),
        {"schema": "app"},
    )

    human_override_id: Mapped[uuid.UUID] = uuid_pk()
    entity_type: Mapped[str] = enum_text(e.FactEntityType, "entity_type", nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    field_name: Mapped[str] = mapped_column(Text, nullable=False)
    override_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    override_status: Mapped[str] = enum_text(
        e.OverrideStatus,
        "override_status",
        nullable=False,
        server_default=e.OverrideStatus.ACTIVE.value,
    )
    reason_code: Mapped[str] = enum_text(e.OverrideReasonCode, "reason_code", nullable=False)
    reason_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created_at()
    superseded_at: Mapped[datetime | None]
    review_on_new_conflict: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )


class ReviewIssue(Base):
    __tablename__ = "review_issue"
    __table_args__ = (
        Index(
            "ix_review_issue_open", "severity", "status", postgresql_where=text("status = 'OPEN'")
        ),
        {"schema": "app"},
    )

    review_issue_id: Mapped[uuid.UUID] = uuid_pk()
    entity_type: Mapped[str] = enum_text(e.FactEntityType, "entity_type", nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    issue_type: Mapped[str] = enum_text(e.ReviewIssueType, "issue_type", nullable=False)
    severity: Mapped[str] = enum_text(e.ReviewIssueSeverity, "severity", nullable=False)
    status: Mapped[str] = enum_text(
        e.ReviewIssueStatus, "status", nullable=False, server_default=e.ReviewIssueStatus.OPEN.value
    )
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = created_at()
    resolved_at: Mapped[datetime | None]
    resolved_by: Mapped[str | None]
    resolution_note: Mapped[str | None]


class MarketingSelection(Base):
    """Current manual marketing-selection state; one row per listing (02 §19.1).

    State-change history goes to audit.action_log. Never written by automatic jobs.
    """

    __tablename__ = "marketing_selection"
    __table_args__ = (
        UniqueConstraint("canonical_listing_id"),
        {"schema": "app"},
    )

    marketing_selection_id: Mapped[uuid.UUID] = uuid_pk()
    canonical_listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.canonical_listing.canonical_listing_id"), nullable=False
    )
    selection_status: Mapped[str] = enum_text(e.SelectionStatus, "selection_status", nullable=False)
    selected_by: Mapped[str] = mapped_column(Text, nullable=False)
    selected_at: Mapped[datetime] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = updated_at()
    note: Mapped[str | None]
    listing_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class ClientSearchPreset(Base):
    """Saved client search: label/pseudonym, versioned filter JSON, optional map
    geometry (08 §16.3). Never stores client contact information."""

    __tablename__ = "client_search_preset"
    __table_args__ = ({"schema": "app"},)

    client_search_preset_id: Mapped[uuid.UUID] = uuid_pk()
    label: Mapped[str] = mapped_column(Text, unique=True, nullable=False)  # pseudonym only
    filter_definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    filter_schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    map_geometry = mapped_column(
        Geography(geometry_type="GEOMETRY", srid=4326, spatial_index=True), nullable=True
    )
    note: Mapped[str | None]
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()
    archived_at: Mapped[datetime | None]


class ClientShortlistEntry(Base):
    """Manual shortlist membership for one preset/client label.

    Live filter matches are computed at read time and never persisted here;
    only an explicit human inclusion/exclusion creates a row (08 §16.3).
    Independent of app.marketing_selection by design.
    """

    __tablename__ = "client_shortlist_entry"
    __table_args__ = (
        UniqueConstraint("client_search_preset_id", "canonical_listing_id"),
        {"schema": "app"},
    )

    client_shortlist_entry_id: Mapped[uuid.UUID] = uuid_pk()
    client_search_preset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("app.client_search_preset.client_search_preset_id"),
        nullable=False,
    )
    canonical_listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.canonical_listing.canonical_listing_id"), nullable=False
    )
    entry_status: Mapped[str] = enum_text(e.ShortlistEntryStatus, "entry_status", nullable=False)
    added_by: Mapped[str] = mapped_column(Text, nullable=False)
    added_at: Mapped[datetime] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = updated_at()
    note: Mapped[str | None]


class AuditActionLog(Base):
    """Append-only record of human/admin actions (06 §26)."""

    __tablename__ = "action_log"
    __table_args__ = (
        Index("ix_action_log_target", "target_type", "target_id", text("recorded_at DESC")),
        {"schema": "audit"},
    )

    action_log_id: Mapped[uuid.UUID] = uuid_pk()
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    actor_type: Mapped[str] = enum_text(e.ActorType, "actor_type", nullable=False)
    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    before_values: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after_values: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    reason: Mapped[str | None]
    correlation_id: Mapped[str | None]
    recorded_at: Mapped[datetime] = created_at()
