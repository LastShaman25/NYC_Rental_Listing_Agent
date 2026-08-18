"""Media assets, variants, associations, analysis, and duplicate groups (02 §14, 05 §7).

Bytes live on the local filesystem beneath the configured media root; the
database stores relative paths (07 §24.1). ``marketing_selected`` is human-set
only — enforced at the service layer and by tests (05 §21.3).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from rental_agent.contracts import enums as e
from rental_agent.db.base import Base, created_at, enum_text, updated_at, uuid_pk


class MediaAsset(Base):
    __tablename__ = "media_asset"
    __table_args__ = (
        Index("ix_media_asset_content_hash", "content_hash"),
        Index("ix_media_asset_perceptual_hash", "perceptual_hash"),
        {"schema": "app"},
    )

    media_asset_id: Mapped[uuid.UUID] = uuid_pk()
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.source.source_id"), nullable=False
    )
    source_observation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.source_observation.source_observation_id")
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    storage_ref: Mapped[str | None]  # relative path under local_data/media
    retrieved_at: Mapped[datetime | None]
    availability_status: Mapped[str] = enum_text(
        e.MediaAvailabilityStatus,
        "availability_status",
        nullable=False,
        server_default=e.MediaAvailabilityStatus.REFERENCED.value,
    )
    media_type: Mapped[str] = enum_text(
        e.MediaType, "media_type", nullable=False, server_default=e.MediaType.UNKNOWN.value
    )
    mime_type: Mapped[str | None]
    width_px: Mapped[int | None] = mapped_column(Integer)
    height_px: Mapped[int | None] = mapped_column(Integer)
    byte_size: Mapped[int | None] = mapped_column(BigInteger)
    content_hash: Mapped[str | None]
    perceptual_hash: Mapped[str | None]
    classification_status: Mapped[str] = enum_text(
        e.MediaClassificationStatus,
        "classification_status",
        nullable=False,
        server_default=e.MediaClassificationStatus.UNCLASSIFIED.value,
    )
    model_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.model_execution.model_execution_id")
    )
    policy_version: Mapped[str] = mapped_column(Text, nullable=False)
    # 05 §7.1 extensions
    source_media_id: Mapped[str | None]
    source_caption: Mapped[str | None]
    source_alt_text: Mapped[str | None]
    final_url_hash: Mapped[str | None]
    retrieval_status_code: Mapped[int | None] = mapped_column(Integer)
    original_filename: Mapped[str | None]
    color_space: Mapped[str | None]
    orientation: Mapped[int | None] = mapped_column(Integer)
    page_count: Mapped[int | None] = mapped_column(Integer)
    has_alpha: Mapped[bool | None] = mapped_column(Boolean)
    animation_detected: Mapped[bool | None] = mapped_column(Boolean)
    technical_quality_status: Mapped[str] = enum_text(
        e.TechnicalQualityStatus,
        "technical_quality_status",
        nullable=False,
        server_default=e.TechnicalQualityStatus.PENDING.value,
    )
    content_safety_status: Mapped[str] = enum_text(
        e.ContentSafetyStatus,
        "content_safety_status",
        nullable=False,
        server_default=e.ContentSafetyStatus.PENDING.value,
    )
    contact_overlay_status: Mapped[str] = enum_text(
        e.ContactOverlayStatus,
        "contact_overlay_status",
        nullable=False,
        server_default=e.ContactOverlayStatus.NOT_DETECTED.value,
    )
    watermark_status: Mapped[str] = enum_text(
        e.WatermarkStatus,
        "watermark_status",
        nullable=False,
        server_default=e.WatermarkStatus.UNKNOWN.value,
    )
    marketing_use_status: Mapped[str] = enum_text(
        e.MarketingUseStatus,
        "marketing_use_status",
        nullable=False,
        server_default=e.MarketingUseStatus.UNKNOWN.value,
    )
    marketing_selected: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    policy_expires_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class MediaVariant(Base):
    __tablename__ = "media_variant"
    __table_args__ = ({"schema": "app"},)

    media_variant_id: Mapped[uuid.UUID] = uuid_pk()
    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.media_asset.media_asset_id"), nullable=False
    )
    variant_type: Mapped[str] = enum_text(e.MediaVariantType, "variant_type", nullable=False)
    storage_ref: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    width_px: Mapped[int | None] = mapped_column(Integer)
    height_px: Mapped[int | None] = mapped_column(Integer)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    transform_version: Mapped[str] = mapped_column(Text, nullable=False)
    use_scope: Mapped[str] = enum_text(
        e.MediaVariantUseScope,
        "use_scope",
        nullable=False,
        server_default=e.MediaVariantUseScope.INTERNAL_REVIEW_ONLY.value,
    )
    created_at: Mapped[datetime] = created_at()


class MediaAssociation(Base):
    __tablename__ = "media_association"
    __table_args__ = ({"schema": "app"},)

    media_association_id: Mapped[uuid.UUID] = uuid_pk()
    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.media_asset.media_asset_id"), nullable=False
    )
    building_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.building.building_id")
    )
    unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.unit.unit_id")
    )
    canonical_listing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.canonical_listing.canonical_listing_id")
    )
    layout_class: Mapped[str | None] = enum_text(e.LayoutClass, "layout_class", nullable=True)
    association_level: Mapped[str] = enum_text(
        e.AssociationLevel, "association_level", nullable=False
    )
    association_status: Mapped[str] = enum_text(
        e.AssociationStatus, "association_status", nullable=False
    )
    confidence: Mapped[str] = enum_text(e.Confidence, "confidence", nullable=False)
    display_order: Mapped[int | None] = mapped_column(Integer)
    is_primary_candidate: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = created_at()


class MediaAnalysis(Base):
    __tablename__ = "media_analysis"
    __table_args__ = ({"schema": "app"},)

    media_analysis_id: Mapped[uuid.UUID] = uuid_pk()
    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.media_asset.media_asset_id"), nullable=False
    )
    analysis_type: Mapped[str] = enum_text(e.MediaAnalysisType, "analysis_type", nullable=False)
    analysis_version: Mapped[str] = mapped_column(Text, nullable=False)
    model_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops.model_execution.model_execution_id")
    )
    result_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[str] = enum_text(e.Confidence, "confidence", nullable=False)
    validation_status: Mapped[str] = enum_text(
        e.ValidationStatus,
        "validation_status",
        nullable=False,
        server_default=e.ValidationStatus.PENDING.value,
    )
    created_at: Mapped[datetime] = created_at()
    superseded_at: Mapped[datetime | None]


class MediaDuplicateGroup(Base):
    __tablename__ = "media_duplicate_group"
    __table_args__ = ({"schema": "app"},)

    media_duplicate_group_id: Mapped[uuid.UUID] = uuid_pk()
    duplicate_type: Mapped[str] = enum_text(e.MediaDuplicateType, "duplicate_type", nullable=False)
    canonical_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.media_asset.media_asset_id")
    )
    method_version: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created_at()


class MediaDuplicateMember(Base):
    __tablename__ = "media_duplicate_member"
    __table_args__ = (
        UniqueConstraint("media_duplicate_group_id", "media_asset_id"),
        {"schema": "app"},
    )

    media_duplicate_member_id: Mapped[uuid.UUID] = uuid_pk()
    media_duplicate_group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("app.media_duplicate_group.media_duplicate_group_id"),
        nullable=False,
    )
    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.media_asset.media_asset_id"), nullable=False
    )
    similarity: Mapped[float | None] = mapped_column(Numeric(6, 5))
    relationship: Mapped[str] = enum_text(
        e.MediaDuplicateRelationship, "relationship", nullable=False
    )
    status: Mapped[str] = enum_text(e.MediaDuplicateMemberStatus, "status", nullable=False)
