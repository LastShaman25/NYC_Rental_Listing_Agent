"""Canonical buildings, units, listings, source links, merges, duplicates (02 §8–9)."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from rental_agent.contracts import enums as e
from rental_agent.db.base import Base, created_at, enum_text, updated_at, uuid_pk


class Building(Base):
    __tablename__ = "building"
    __table_args__ = ({"schema": "app"},)

    building_id: Mapped[uuid.UUID] = uuid_pk()
    address_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.address.address_id"), nullable=False
    )
    canonical_name: Mapped[str | None]
    property_type: Mapped[str] = enum_text(
        e.PropertyType, "property_type", nullable=False, server_default=e.PropertyType.UNKNOWN.value
    )
    identity_status: Mapped[str] = enum_text(
        e.BuildingIdentityStatus,
        "identity_status",
        nullable=False,
        server_default=e.BuildingIdentityStatus.PROVISIONAL.value,
    )
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class Unit(Base):
    __tablename__ = "unit"
    __table_args__ = (
        Index("ix_unit_building_fingerprint", "building_id", "unit_fingerprint"),
        {"schema": "app"},
    )

    unit_id: Mapped[uuid.UUID] = uuid_pk()
    building_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.building.building_id"), nullable=False
    )
    canonical_unit_label: Mapped[str | None]
    unit_fingerprint: Mapped[str | None]
    floor_label: Mapped[str | None]
    layout_class: Mapped[str] = enum_text(
        e.LayoutClass, "layout_class", nullable=False, server_default=e.LayoutClass.UNKNOWN.value
    )
    bedroom_count: Mapped[float | None] = mapped_column(Numeric(3, 1))
    bathroom_count: Mapped[float | None] = mapped_column(Numeric(3, 1))
    identity_status: Mapped[str] = enum_text(
        e.UnitIdentityStatus,
        "identity_status",
        nullable=False,
        server_default=e.UnitIdentityStatus.PROVISIONAL.value,
    )
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class CanonicalListing(Base):
    __tablename__ = "canonical_listing"
    __table_args__ = (
        CheckConstraint(
            "monthly_rent_minor IS NULL OR monthly_rent_minor >= 0", name="rent_nonnegative"
        ),
        # Badge invariant (02 §12.3): eligibility only with confirmed in-unit W/D.
        CheckConstraint(
            "indoor_laundry_badge_eligible = false "
            "OR laundry_type = 'IN_UNIT_WASHER_DRYER_CONFIRMED'",
            name="laundry_badge_invariant",
        ),
        Index(
            "ix_canonical_listing_inventory",
            "lifecycle_status",
            "layout_class",
            "monthly_rent_minor",
            text("last_seen_at DESC"),
        ),
        {"schema": "app"},
    )

    canonical_listing_id: Mapped[uuid.UUID] = uuid_pk()
    building_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.building.building_id"), nullable=False
    )
    unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.unit.unit_id")
    )
    layout_class: Mapped[str] = enum_text(
        e.LayoutClass, "layout_class", nullable=False, server_default=e.LayoutClass.UNKNOWN.value
    )
    bedroom_count: Mapped[float | None] = mapped_column(Numeric(3, 1))
    bathroom_count: Mapped[float | None] = mapped_column(Numeric(3, 1))
    monthly_rent_minor: Mapped[int | None] = mapped_column(BigInteger)
    currency_code: Mapped[str] = mapped_column(Text, nullable=False, server_default="USD")
    available_from: Mapped[date | None] = mapped_column(Date)
    availability_status: Mapped[str] = enum_text(
        e.AvailabilityStatus,
        "availability_status",
        nullable=False,
        server_default=e.AvailabilityStatus.UNKNOWN.value,
    )
    lifecycle_status: Mapped[str] = enum_text(
        e.LifecycleStatus,
        "lifecycle_status",
        nullable=False,
        server_default=e.LifecycleStatus.CANDIDATE.value,
    )
    laundry_type: Mapped[str] = enum_text(
        e.LaundryType, "laundry_type", nullable=False, server_default=e.LaundryType.UNKNOWN.value
    )
    indoor_laundry_badge_eligible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    description_current: Mapped[str | None]
    first_seen_at: Mapped[datetime] = mapped_column(nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(nullable=False)
    last_material_change_at: Mapped[datetime] = mapped_column(nullable=False)
    inactive_at: Mapped[datetime | None]
    canonical_resolution_status: Mapped[str] = enum_text(
        e.CanonicalResolutionStatus,
        "canonical_resolution_status",
        nullable=False,
        server_default=e.CanonicalResolutionStatus.PROVISIONAL.value,
    )
    enrichment_status: Mapped[str] = enum_text(
        e.EnrichmentStatus,
        "enrichment_status",
        nullable=False,
        server_default=e.EnrichmentStatus.NOT_STARTED.value,
    )
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class ListingSourceLink(Base):
    __tablename__ = "listing_source_link"
    __table_args__ = (
        Index(
            "uq_listing_source_link_native",
            "source_id",
            "source_native_id",
            unique=True,
            postgresql_where=text("source_native_id IS NOT NULL"),
        ),
        Index(
            "ix_listing_source_link_status",
            "source_id",
            "link_status",
            text("last_seen_at DESC"),
        ),
        {"schema": "app"},
    )

    listing_source_link_id: Mapped[uuid.UUID] = uuid_pk()
    canonical_listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.canonical_listing.canonical_listing_id"), nullable=False
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.source.source_id"), nullable=False
    )
    source_native_id: Mapped[str | None]
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    first_observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("raw.source_observation.source_observation_id"),
        nullable=False,
    )
    latest_observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("raw.source_observation.source_observation_id"),
        nullable=False,
    )
    first_seen_at: Mapped[datetime] = mapped_column(nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(nullable=False)
    link_status: Mapped[str] = enum_text(
        e.LinkStatus, "link_status", nullable=False, server_default=e.LinkStatus.ACTIVE.value
    )
    # B3 (03 §5.4): search-index links cannot support disappearance evidence.
    discovery_method: Mapped[str] = enum_text(
        e.DiscoveryMethod,
        "discovery_method",
        nullable=False,
        server_default=e.DiscoveryMethod.UNKNOWN.value,
    )
    identity_method: Mapped[str] = enum_text(e.IdentityMethod, "identity_method", nullable=False)
    identity_confidence: Mapped[str] = enum_text(
        e.IdentityConfidence, "identity_confidence", nullable=False
    )
    identity_rule_version: Mapped[str] = mapped_column(Text, nullable=False)


class CanonicalMerge(Base):
    __tablename__ = "canonical_merge"
    __table_args__ = ({"schema": "app"},)

    canonical_merge_id: Mapped[uuid.UUID] = uuid_pk()
    source_listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.canonical_listing.canonical_listing_id"), nullable=False
    )
    target_listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.canonical_listing.canonical_listing_id"), nullable=False
    )
    reason_code: Mapped[str] = enum_text(e.MergeReasonCode, "reason_code", nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    performed_by_type: Mapped[str] = enum_text(
        e.PerformedByType, "performed_by_type", nullable=False
    )
    performed_by: Mapped[str | None]
    performed_at: Mapped[datetime] = mapped_column(nullable=False)
    reversed_at: Mapped[datetime | None]


class DuplicateCandidate(Base):
    __tablename__ = "duplicate_candidate"
    __table_args__ = (
        UniqueConstraint("listing_a_id", "listing_b_id", "rule_version"),
        CheckConstraint("listing_a_id <> listing_b_id", name="distinct_listings"),
        {"schema": "app"},
    )

    duplicate_candidate_id: Mapped[uuid.UUID] = uuid_pk()
    listing_a_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.canonical_listing.canonical_listing_id"), nullable=False
    )
    listing_b_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.canonical_listing.canonical_listing_id"), nullable=False
    )
    # Internal identity-match measure only; never a user-facing quality score (02 §9.4).
    candidate_score: Mapped[float | None] = mapped_column(Numeric(6, 5))
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    rule_version: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = enum_text(
        e.DuplicateCandidateStatus,
        "status",
        nullable=False,
        server_default=e.DuplicateCandidateStatus.PENDING.value,
    )
    resolved_by: Mapped[str | None]
    resolved_at: Mapped[datetime | None]
