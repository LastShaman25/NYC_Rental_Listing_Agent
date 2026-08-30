"""Transit stops, routes, listing access options, destinations, commutes (02 §15–16).

transit_service_calendar (06 §6.7) is deferred to Phase 4 dataset ingestion.
No field here is, or may become, a transit/commute quality score.
"""

import uuid
from datetime import datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from rental_agent.contracts import enums as e
from rental_agent.db.base import Base, created_at, enum_text, updated_at, uuid_pk


class TransitStop(Base):
    __tablename__ = "transit_stop"
    __table_args__ = (
        UniqueConstraint("provider_source_id", "provider_stop_id", "dataset_version"),
        {"schema": "app"},
    )

    transit_stop_id: Mapped[uuid.UUID] = uuid_pk()
    provider_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.source.source_id"), nullable=False
    )
    provider_stop_id: Mapped[str] = mapped_column(Text, nullable=False)
    parent_stop_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.transit_stop.transit_stop_id")
    )
    operator_code: Mapped[str] = mapped_column(Text, nullable=False)
    stop_name: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = enum_text(e.TransitMode, "mode", nullable=False)
    location_point = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=True), nullable=False
    )
    active_status: Mapped[str] = enum_text(
        e.TransitStopActiveStatus,
        "active_status",
        nullable=False,
        server_default=e.TransitStopActiveStatus.UNKNOWN.value,
    )
    dataset_version: Mapped[str] = mapped_column(Text, nullable=False)


class TransitRoute(Base):
    __tablename__ = "transit_route"
    __table_args__ = (
        UniqueConstraint("provider_source_id", "provider_route_id", "dataset_version"),
        {"schema": "app"},
    )

    transit_route_id: Mapped[uuid.UUID] = uuid_pk()
    provider_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.source.source_id"), nullable=False
    )
    provider_route_id: Mapped[str] = mapped_column(Text, nullable=False)
    operator_code: Mapped[str] = mapped_column(Text, nullable=False)
    route_short_name: Mapped[str | None]
    route_long_name: Mapped[str | None]
    mode: Mapped[str] = enum_text(e.TransitMode, "mode", nullable=False)
    dataset_version: Mapped[str] = mapped_column(Text, nullable=False)


class TransitStopRoute(Base):
    """Stop-to-route service relationship from the transit dataset (06 §6.7)."""

    __tablename__ = "transit_stop_route"
    __table_args__ = (
        UniqueConstraint("transit_stop_id", "transit_route_id"),
        {"schema": "app"},
    )

    transit_stop_route_id: Mapped[uuid.UUID] = uuid_pk()
    transit_stop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.transit_stop.transit_stop_id"), nullable=False
    )
    transit_route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.transit_route.transit_route_id"), nullable=False
    )
    dataset_version: Mapped[str] = mapped_column(Text, nullable=False)


class TransitAccess(Base):
    __tablename__ = "transit_access"
    __table_args__ = (
        CheckConstraint(
            "walking_distance_m IS NULL OR walking_distance_m >= 0", name="walk_dist_nonneg"
        ),
        CheckConstraint(
            "walking_duration_s IS NULL OR walking_duration_s >= 0", name="walk_dur_nonneg"
        ),
        {"schema": "app"},
    )

    transit_access_id: Mapped[uuid.UUID] = uuid_pk()
    canonical_listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.canonical_listing.canonical_listing_id"), nullable=False
    )
    transit_stop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.transit_stop.transit_stop_id"), nullable=False
    )
    mode: Mapped[str] = enum_text(e.TransitMode, "mode", nullable=False)
    straight_line_distance_m: Mapped[int | None] = mapped_column(Integer)
    walking_distance_m: Mapped[int | None] = mapped_column(Integer)
    walking_duration_s: Mapped[int | None] = mapped_column(Integer)
    route_provider_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.provider_request.provider_request_id")
    )
    proximity_rank: Mapped[int | None] = mapped_column(
        Integer
    )  # deterministic ordering, not quality
    usefulness_status: Mapped[str] = enum_text(
        e.UsefulnessStatus,
        "usefulness_status",
        nullable=False,
        server_default=e.UsefulnessStatus.UNRESOLVED.value,
    )
    usefulness_reasons: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    meaningful_connections: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    validation_status: Mapped[str] = enum_text(
        e.TransitValidationStatus,
        "validation_status",
        nullable=False,
        server_default=e.TransitValidationStatus.PENDING.value,
    )
    validation_reasons: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    input_location_hash: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_version: Mapped[str] = mapped_column(Text, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(nullable=False)
    expires_at: Mapped[datetime | None]


class TransitAccessRoute(Base):
    __tablename__ = "transit_access_route"
    __table_args__ = (
        UniqueConstraint("transit_access_id", "transit_route_id"),
        {"schema": "app"},
    )

    transit_access_route_id: Mapped[uuid.UUID] = uuid_pk()
    transit_access_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.transit_access.transit_access_id"), nullable=False
    )
    transit_route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.transit_route.transit_route_id"), nullable=False
    )
    direction_or_headsign: Mapped[str | None]
    service_status: Mapped[str] = enum_text(
        e.TransitServiceStatus,
        "service_status",
        nullable=False,
        server_default=e.TransitServiceStatus.UNKNOWN.value,
    )


class Destination(Base):
    __tablename__ = "destination"
    __table_args__ = ({"schema": "app"},)

    destination_id: Mapped[uuid.UUID] = uuid_pk()
    destination_code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    destination_type: Mapped[str] = enum_text(e.DestinationType, "destination_type", nullable=False)
    institution_name: Mapped[str | None]
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    routing_anchor_name: Mapped[str] = mapped_column(Text, nullable=False)
    routing_anchor_point = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=True), nullable=False
    )
    address_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.address.address_id")
    )
    active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))
    registry_version: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class CommuteResult(Base):
    __tablename__ = "commute_result"
    __table_args__ = (
        CheckConstraint("duration_s IS NULL OR duration_s >= 0", name="duration_nonneg"),
        CheckConstraint("distance_m IS NULL OR distance_m >= 0", name="distance_nonneg"),
        CheckConstraint("transfer_count IS NULL OR transfer_count >= 0", name="transfers_nonneg"),
        # AVAILABLE requires a duration (02 §16.3).
        CheckConstraint(
            "result_status <> 'AVAILABLE' OR duration_s IS NOT NULL "
            "OR (duration_min_s IS NOT NULL AND duration_max_s IS NOT NULL)",
            name="available_requires_duration",
        ),
        # B7 (04 §19A): a researched estimate must cite web sources and link its
        # research execution; a provider route must link its provider request.
        CheckConstraint(
            "result_type <> 'RESEARCHED_ESTIMATE' OR (model_execution_id IS NOT NULL "
            "AND sources IS NOT NULL AND jsonb_array_length(sources) > 0)",
            name="research_requires_sources",
        ),
        CheckConstraint(
            "result_type <> 'PROVIDER_ROUTE' OR provider_request_id IS NOT NULL",
            name="provider_route_requires_request",
        ),
        CheckConstraint(
            "duration_min_s IS NULL OR duration_max_s IS NULL OR duration_min_s <= duration_max_s",
            name="duration_range_ordered",
        ),
        # A commute targets EITHER a canonical listing OR a company portfolio
        # property (owner request 2026-08-30) — exactly one.
        CheckConstraint(
            "num_nonnulls(canonical_listing_id, company_property_id) = 1",
            name="exactly_one_target",
        ),
        {"schema": "app"},
    )

    commute_result_id: Mapped[uuid.UUID] = uuid_pk()
    canonical_listing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.canonical_listing.canonical_listing_id")
    )
    company_property_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("app.company_property.company_property_id", ondelete="CASCADE"),
    )
    destination_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.destination.destination_id"), nullable=False
    )
    result_type: Mapped[str] = enum_text(
        e.CommuteResultType,
        "result_type",
        nullable=False,
        server_default=e.CommuteResultType.RESEARCHED_ESTIMATE.value,
    )
    provider_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.provider_request.provider_request_id")
    )
    model_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.model_execution.model_execution_id")
    )
    travel_mode: Mapped[str] = enum_text(
        e.TravelMode,
        "travel_mode",
        nullable=False,
        server_default=e.TravelMode.PUBLIC_TRANSIT.value,
    )
    time_basis: Mapped[str] = enum_text(e.TimeBasis, "time_basis", nullable=False)
    requested_local_datetime: Mapped[datetime | None]
    duration_s: Mapped[int | None] = mapped_column(Integer)
    duration_min_s: Mapped[int | None] = mapped_column(Integer)
    duration_max_s: Mapped[int | None] = mapped_column(Integer)
    distance_m: Mapped[int | None] = mapped_column(Integer)
    transfer_count: Mapped[int | None] = mapped_column(Integer)
    route_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    sources: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    confidence: Mapped[str] = enum_text(
        e.Confidence, "confidence", nullable=False, server_default=e.Confidence.UNKNOWN.value
    )
    result_status: Mapped[str] = enum_text(e.CommuteResultStatus, "result_status", nullable=False)
    validation_status: Mapped[str] = enum_text(
        e.TransitValidationStatus,
        "validation_status",
        nullable=False,
        server_default=e.TransitValidationStatus.PENDING.value,
    )
    validation_reasons: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    input_location_hash: Mapped[str] = mapped_column(Text, nullable=False)
    destination_registry_version: Mapped[str] = mapped_column(Text, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(nullable=False)
    expires_at: Mapped[datetime | None]
