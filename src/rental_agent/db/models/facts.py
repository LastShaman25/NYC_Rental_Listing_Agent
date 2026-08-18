"""Fact assertions, resolutions, amenities, listing events, and field history (02 §10, §13, §17)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from rental_agent.contracts import enums as e
from rental_agent.db.base import Base, created_at, enum_text, uuid_pk


class FactAssertion(Base):
    __tablename__ = "fact_assertion"
    __table_args__ = (
        Index(
            "ix_fact_assertion_entity",
            "entity_type",
            "entity_id",
            "fact_key",
            text("asserted_at DESC"),
        ),
        {"schema": "app"},
    )

    fact_assertion_id: Mapped[uuid.UUID] = uuid_pk()
    entity_type: Mapped[str] = enum_text(e.FactEntityType, "entity_type", nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    fact_key: Mapped[str] = mapped_column(Text, nullable=False)
    value_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    value_status: Mapped[str] = enum_text(e.ValueStatus, "value_status", nullable=False)
    derivation_type: Mapped[str] = enum_text(e.DerivationType, "derivation_type", nullable=False)
    source_observation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.source_observation.source_observation_id")
    )
    media_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.media_asset.media_asset_id")
    )
    provider_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.provider_request.provider_request_id")
    )
    evidence_text: Mapped[str | None]
    evidence_locator: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    confidence: Mapped[str] = enum_text(e.Confidence, "confidence", nullable=False)
    validation_status: Mapped[str] = enum_text(
        e.ValidationStatus,
        "validation_status",
        nullable=False,
        server_default=e.ValidationStatus.PENDING.value,
    )
    model_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.model_execution.model_execution_id")
    )
    asserted_at: Mapped[datetime] = created_at()
    superseded_at: Mapped[datetime | None]


class FactResolution(Base):
    __tablename__ = "fact_resolution"
    __table_args__ = (
        # Only one current (non-superseded) resolution per fact (02 §10.2).
        Index(
            "uq_fact_resolution_current",
            "entity_type",
            "entity_id",
            "fact_key",
            unique=True,
            postgresql_where=text("superseded_at IS NULL"),
        ),
        {"schema": "app"},
    )

    fact_resolution_id: Mapped[uuid.UUID] = uuid_pk()
    entity_type: Mapped[str] = enum_text(e.FactEntityType, "entity_type", nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    fact_key: Mapped[str] = mapped_column(Text, nullable=False)
    effective_assertion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.fact_assertion.fact_assertion_id")
    )
    resolution_status: Mapped[str] = enum_text(
        e.ResolutionStatus, "resolution_status", nullable=False
    )
    resolution_method: Mapped[str] = enum_text(
        e.ResolutionMethod, "resolution_method", nullable=False
    )
    resolution_rule_version: Mapped[str] = mapped_column(Text, nullable=False)
    resolved_at: Mapped[datetime] = created_at()
    superseded_at: Mapped[datetime | None]


class AmenityDefinition(Base):
    __tablename__ = "amenity_definition"
    __table_args__ = ({"schema": "app"},)

    amenity_definition_id: Mapped[uuid.UUID] = uuid_pk()
    amenity_code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = enum_text(e.AmenityScope, "scope", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class AmenityAssertion(Base):
    __tablename__ = "amenity_assertion"
    __table_args__ = ({"schema": "app"},)

    amenity_assertion_id: Mapped[uuid.UUID] = uuid_pk()
    canonical_listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.canonical_listing.canonical_listing_id"), nullable=False
    )
    amenity_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("app.amenity_definition.amenity_definition_id"),
        nullable=False,
    )
    asserted_scope: Mapped[str] = enum_text(e.AssertedScope, "asserted_scope", nullable=False)
    presence_status: Mapped[str] = enum_text(e.PresenceStatus, "presence_status", nullable=False)
    fact_assertion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.fact_assertion.fact_assertion_id"), nullable=False
    )
    effective: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class ListingEvent(Base):
    __tablename__ = "listing_event"
    __table_args__ = (
        Index("ix_listing_event_listing_time", "canonical_listing_id", text("event_time DESC")),
        {"schema": "app"},
    )

    listing_event_id: Mapped[uuid.UUID] = uuid_pk()
    canonical_listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.canonical_listing.canonical_listing_id"), nullable=False
    )
    event_type: Mapped[str] = enum_text(e.ListingEventType, "event_type", nullable=False)
    event_time: Mapped[datetime] = mapped_column(nullable=False)
    recorded_at: Mapped[datetime] = created_at()
    refresh_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.refresh_run.refresh_run_id")
    )
    source_observation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.source_observation.source_observation_id")
    )
    before_values: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after_values: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    reason_codes: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    idempotency_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)


class ListingFieldHistory(Base):
    __tablename__ = "listing_field_history"
    __table_args__ = (
        Index(
            "ix_listing_field_history_field",
            "canonical_listing_id",
            "field_name",
            text("valid_from DESC"),
        ),
        {"schema": "app"},
    )

    listing_field_history_id: Mapped[uuid.UUID] = uuid_pk()
    canonical_listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.canonical_listing.canonical_listing_id"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(Text, nullable=False)
    value_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    valid_from: Mapped[datetime] = mapped_column(nullable=False)
    valid_to: Mapped[datetime | None]
    fact_resolution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.fact_resolution.fact_resolution_id")
    )
    listing_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.listing_event.listing_event_id"), nullable=False
    )
