"""Company property portfolio (owner request 2026-08-29).

The owner's company circulates a docx/pdf sheet of property names + listing
links. The portal (webui /company) parses that file into rows here; the
company-refresh job then checks each property's page for available units,
repairing dead links via the building's official website or StreetEasy search.
Rows are matched to canonical inventory buildings (by address fingerprint) so
company properties can be highlighted on the map.

This registry is deliberately OUTSIDE the acquisition pipeline: rows are
owner-supplied reference data with availability snapshots, not canonical
listings; nothing here feeds facts or lifecycle.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from rental_agent.db.base import Base, created_at, updated_at, uuid_pk

# link_status: UNCHECKED | OK | REPLACED | FAILED
# resolved_url_kind: ORIGINAL | OFFICIAL_SITE | STREETEASY
# check_status: PENDING | CHECKED | FAILED


class CompanyProperty(Base):
    __tablename__ = "company_property"
    __table_args__ = (
        UniqueConstraint("name_fingerprint"),
        {"schema": "app"},
    )

    company_property_id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # Lowercased/collapsed match key so re-uploads update rather than duplicate.
    name_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    source_document: Mapped[str] = mapped_column(Text, nullable=False)
    original_url: Mapped[str | None]
    resolved_url: Mapped[str | None]
    resolved_url_kind: Mapped[str | None]
    link_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="UNCHECKED")
    address_text: Mapped[str | None]
    locality: Mapped[str | None]
    latitude: Mapped[float | None]
    longitude: Mapped[float | None]
    matched_building_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app.building.building_id", ondelete="SET NULL")
    )
    # Availability snapshot from the last successful page check:
    # {"available_units": [...], "no_units_stated": bool, "evidence": str,
    #  "source_url": str, "checked_at": iso, plus page facts: laundry_type,
    #  amenities, fee_status, description, floor_plan_*, nearby_transit}
    availability: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # Rolling check history (newest first, capped): one entry per completed
    # check with unit/rent deltas — the company analogue of listing events
    # (07 §11: detail pages expose history; owner request 2026-08-30).
    check_log: Mapped[list[Any] | None] = mapped_column(JSONB)
    check_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="PENDING")
    check_error: Mapped[str | None]
    last_checked_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()
