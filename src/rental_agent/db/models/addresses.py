"""Addresses with PostGIS geometry and address assertions (02 §7)."""

import uuid
from datetime import datetime

from geoalchemy2 import Geography
from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from rental_agent.contracts import enums as e
from rental_agent.db.base import Base, created_at, enum_text, updated_at, uuid_pk


class Address(Base):
    __tablename__ = "address"
    __table_args__ = (
        Index("ix_address_fingerprint", "address_fingerprint"),
        {"schema": "app"},
    )

    address_id: Mapped[uuid.UUID] = uuid_pk()
    address_line_1: Mapped[str | None]
    address_line_2: Mapped[str | None]
    locality: Mapped[str] = mapped_column(Text, nullable=False)
    administrative_area: Mapped[str] = mapped_column(Text, nullable=False)  # NY | NJ
    postal_code: Mapped[str | None]
    country_code: Mapped[str] = mapped_column(Text, nullable=False, server_default="US")
    borough: Mapped[str | None]
    neighborhood: Mapped[str | None]  # display label, never identity
    formatted_address: Mapped[str] = mapped_column(Text, nullable=False)
    address_fingerprint: Mapped[str | None]
    location_point = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=True), nullable=True
    )
    location_precision: Mapped[str] = enum_text(
        e.LocationPrecision,
        "location_precision",
        nullable=False,
        server_default=e.LocationPrecision.UNKNOWN.value,
    )
    geocoder_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.source.source_id")
    )
    geocoder_result_id: Mapped[str | None]
    geocoded_at: Mapped[datetime | None]
    geocode_input_hash: Mapped[str | None]
    geocode_status: Mapped[str] = enum_text(
        e.GeocodeStatus,
        "geocode_status",
        nullable=False,
        server_default=e.GeocodeStatus.PENDING.value,
    )
    boundary_status: Mapped[str] = enum_text(
        e.BoundaryStatus,
        "boundary_status",
        nullable=False,
        server_default=e.BoundaryStatus.UNRESOLVED.value,
    )
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class AddressAssertion(Base):
    __tablename__ = "address_assertion"
    __table_args__ = ({"schema": "app"},)

    address_assertion_id: Mapped[uuid.UUID] = uuid_pk()
    address_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.address.address_id"), nullable=False
    )
    source_observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("raw.source_observation.source_observation_id"),
        nullable=False,
    )
    raw_address_text: Mapped[str | None]
    unit_text: Mapped[str | None]
    assertion_status: Mapped[str] = enum_text(
        e.AddressAssertionStatus, "assertion_status", nullable=False
    )
    match_method: Mapped[str] = enum_text(e.AddressMatchMethod, "match_method", nullable=False)
    confidence: Mapped[str] = enum_text(e.Confidence, "confidence", nullable=False)
    recorded_at: Mapped[datetime] = created_at()
