"""Point-in-time CSV export with relational companion files (02 §23, 06 §28).

One snapshot-consistent export run produces a directory:
    listings.csv  sources.csv  transit.csv  commutes.csv  history.csv

Rules enforced here: UTF-8, formula-injection protection on untrusted text,
canonical listing IDs in every file, no contact data (none exists in schema),
no secrets/signed URLs, unknown/conflict states passed through verbatim.
"""

import csv
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from rental_agent.config.logging import get_logger
from rental_agent.db.models import (
    Address,
    Building,
    CanonicalListing,
    CommuteResult,
    Destination,
    ListingEvent,
    ListingSourceLink,
    MarketingSelection,
    Source,
    TransitAccess,
    TransitStop,
)

log = get_logger(__name__)

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t")


def _safe(value) -> str:
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(_FORMULA_PREFIXES) else text


def _write(path: Path, header: list[str], rows: list[list]) -> int:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for row in rows:
            writer.writerow([_safe(cell) for cell in row])
    return len(rows)


@dataclass
class ExportResult:
    directory: Path
    counts: dict[str, int]


def export_listings(
    session: Session,
    export_root: Path,
    *,
    listing_ids: list[uuid.UUID] | None = None,
    export_type: str = "inventory",
) -> ExportResult:
    """Export the given listings (or all) with companion files."""
    stamp = datetime.now(tz=UTC)
    directory = export_root / f"{stamp:%Y-%m-%d_%H%M}_{export_type}_{uuid.uuid4().hex[:6]}"
    directory.mkdir(parents=True, exist_ok=True)

    listing_query = (
        select(CanonicalListing, Address, MarketingSelection.selection_status)
        .join(Building, Building.building_id == CanonicalListing.building_id)
        .join(Address, Address.address_id == Building.address_id)
        .outerjoin(
            MarketingSelection,
            MarketingSelection.canonical_listing_id == CanonicalListing.canonical_listing_id,
        )
    )
    if listing_ids is not None:
        listing_query = listing_query.where(CanonicalListing.canonical_listing_id.in_(listing_ids))
    listings = session.execute(listing_query).all()
    ids = [listing.canonical_listing_id for listing, _, _ in listings]

    counts = {}
    counts["listings"] = _write(
        directory / "listings.csv",
        [
            "canonical_listing_id",
            "address",
            "locality",
            "borough",
            "boundary_status",
            "layout_class",
            "bedrooms",
            "bathrooms",
            "monthly_rent_dollars",
            "currency",
            "availability_status",
            "lifecycle_status",
            "laundry_type",
            "indoor_laundry_badge_eligible",
            "location_precision",
            "first_seen_at",
            "last_seen_at",
            "last_material_change_at",
            "enrichment_status",
            "marketing_selected",
        ],
        [
            [
                listing.canonical_listing_id,
                address.formatted_address,
                address.locality,
                address.borough,
                address.boundary_status,
                listing.layout_class,
                listing.bedroom_count,
                listing.bathroom_count,
                (listing.monthly_rent_minor / 100) if listing.monthly_rent_minor else None,
                listing.currency_code,
                listing.availability_status,
                listing.lifecycle_status,
                listing.laundry_type,
                listing.indoor_laundry_badge_eligible,
                address.location_precision,
                listing.first_seen_at.isoformat(),
                listing.last_seen_at.isoformat(),
                listing.last_material_change_at.isoformat(),
                listing.enrichment_status,
                selection == "SELECTED",
            ]
            for listing, address, selection in listings
        ],
    )

    source_rows = session.execute(
        select(ListingSourceLink, Source.source_code)
        .join(Source, Source.source_id == ListingSourceLink.source_id)
        .where(ListingSourceLink.canonical_listing_id.in_(ids))
    ).all()
    counts["sources"] = _write(
        directory / "sources.csv",
        [
            "canonical_listing_id",
            "source_code",
            "source_url",
            "discovery_method",
            "link_status",
            "identity_method",
            "first_seen_at",
            "last_seen_at",
        ],
        [
            [
                link.canonical_listing_id,
                code,
                link.source_url,
                link.discovery_method,
                link.link_status,
                link.identity_method,
                link.first_seen_at.isoformat(),
                link.last_seen_at.isoformat(),
            ]
            for link, code in source_rows
        ],
    )

    transit_rows = session.execute(
        select(TransitAccess, TransitStop.stop_name, TransitStop.operator_code)
        .join(TransitStop, TransitStop.transit_stop_id == TransitAccess.transit_stop_id)
        .where(TransitAccess.canonical_listing_id.in_(ids))
        .order_by(
            TransitAccess.canonical_listing_id, TransitAccess.mode, TransitAccess.proximity_rank
        )
    ).all()
    counts["transit"] = _write(
        directory / "transit.csv",
        [
            "canonical_listing_id",
            "mode",
            "station",
            "operator",
            "straight_line_m",
            "walking_m",
            "walking_minutes",
            "proximity_rank",
            "usefulness_status",
            "validation_status",
        ],
        [
            [
                access.canonical_listing_id,
                access.mode,
                stop_name,
                operator,
                access.straight_line_distance_m,
                access.walking_distance_m,
                (access.walking_duration_s // 60) if access.walking_duration_s else None,
                access.proximity_rank,
                access.usefulness_status,
                access.validation_status,
            ]
            for access, stop_name, operator in transit_rows
        ],
    )

    commute_rows = session.execute(
        select(CommuteResult, Destination.destination_code, Destination.display_name)
        .join(Destination, Destination.destination_id == CommuteResult.destination_id)
        .where(CommuteResult.canonical_listing_id.in_(ids))
    ).all()
    counts["commutes"] = _write(
        directory / "commutes.csv",
        [
            "canonical_listing_id",
            "destination_code",
            "destination",
            "result_type",
            "duration_min_minutes",
            "duration_max_minutes",
            "transfers",
            "confidence",
            "validation_status",
            "source_urls",
            "calculated_at",
            "expires_at",
        ],
        [
            [
                result.canonical_listing_id,
                code,
                name,
                result.result_type,
                (result.duration_min_s // 60) if result.duration_min_s else None,
                (result.duration_max_s // 60) if result.duration_max_s else None,
                result.transfer_count,
                result.confidence,
                result.validation_status,
                " | ".join(s.get("url", "") for s in (result.sources or [])),
                result.calculated_at.isoformat(),
                result.expires_at.isoformat() if result.expires_at else None,
            ]
            for result, code, name in commute_rows
        ],
    )

    event_rows = (
        session.execute(
            select(ListingEvent)
            .where(ListingEvent.canonical_listing_id.in_(ids))
            .order_by(ListingEvent.canonical_listing_id, ListingEvent.event_time)
        )
        .scalars()
        .all()
    )
    counts["history"] = _write(
        directory / "history.csv",
        ["canonical_listing_id", "event_type", "event_time", "before", "after"],
        [
            [
                event.canonical_listing_id,
                event.event_type,
                event.event_time.isoformat(),
                event.before_values,
                event.after_values,
            ]
            for event in event_rows
        ],
    )
    log.info("export_complete", directory=str(directory), **counts)
    return ExportResult(directory=directory, counts=counts)
