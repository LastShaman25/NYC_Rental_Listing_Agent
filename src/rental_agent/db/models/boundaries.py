"""Supported-market boundary registry (04 §9.1; config schema per 06 §5.2).

Versioned polygons for New York City (per borough), Jersey City, Hoboken, and
Fort Lee. Scope decisions come from these geometries, never from source-provided
neighborhood text alone (PR-GEO-001).
"""

import uuid
from datetime import datetime

from geoalchemy2 import Geography
from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from rental_agent.db.base import Base, created_at, uuid_pk


class GeographicBoundary(Base):
    __tablename__ = "geographic_boundary"
    __table_args__ = ({"schema": "config"},)

    geographic_boundary_id: Mapped[uuid.UUID] = uuid_pk()
    region_code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    region_group: Mapped[str] = mapped_column(Text, nullable=False)  # NYC | NJ
    geometry = mapped_column(
        Geography(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=True), nullable=False
    )
    dataset_version: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created_at()
