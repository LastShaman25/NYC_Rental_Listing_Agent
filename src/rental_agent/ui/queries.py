"""Read models for the Streamlit workbench (07 §23.1, 06 §25.1).

Pages call these functions (and the canonical services for writes); UI code
never embeds business rules or raw table edits. All queries are short reads.
"""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from rental_agent.db.models import (
    Address,
    Building,
    CanonicalListing,
    ClientSearchPreset,
    ClientShortlistEntry,
    CommuteResult,
    Destination,
    DuplicateCandidate,
    FactAssertion,
    FactResolution,
    HumanOverride,
    Job,
    ListingEvent,
    ListingSourceLink,
    MarketingSelection,
    MediaAsset,
    MediaAssociation,
    RefreshRun,
    ReviewIssue,
    Source,
    SourceRun,
    TransitAccess,
    TransitStop,
)

LAUNDRY_LABELS = {
    "IN_UNIT_WASHER_DRYER_CONFIRMED": "室内洗烘 (confirmed in-unit W/D)",
    "IN_UNIT_WASHER_ONLY": "In-unit washer only",
    "IN_UNIT_DRYER_ONLY": "In-unit dryer only",
    "IN_UNIT_HOOKUP_ONLY": "Hookups only",
    "BUILDING_SHARED_LAUNDRY": "Building laundry",
    "OFFSITE_OR_NEARBY_LAUNDRY": "Laundry nearby/offsite",
    "NO_LAUNDRY_STATED": "No laundry stated",
    "EXPLICITLY_NO_LAUNDRY": "Explicitly no laundry",
    "CONFLICTING": "Conflicting laundry evidence",
    "UNKNOWN": "Laundry unknown",
}


def laundry_label(laundry_type: str, badge_eligible: bool) -> str:
    # 室内洗烘 only through the badge invariant (07 §9.6).
    if laundry_type == "IN_UNIT_WASHER_DRYER_CONFIRMED" and not badge_eligible:
        return "In-unit W/D (pending validation)"
    return LAUNDRY_LABELS.get(laundry_type, laundry_type)


# -- dashboard -----------------------------------------------------------------


def dashboard_summary(session: Session) -> dict[str, int]:
    listing_counts: dict[str, int] = {
        status: count
        for status, count in session.execute(
            select(CanonicalListing.lifecycle_status, func.count()).group_by(
                CanonicalListing.lifecycle_status
            )
        )
    }
    selected = session.execute(
        select(func.count())
        .select_from(MarketingSelection)
        .where(MarketingSelection.selection_status == "SELECTED")
    ).scalar()
    open_issues = session.execute(
        select(func.count()).select_from(ReviewIssue).where(ReviewIssue.status == "OPEN")
    ).scalar()
    pending_dups = session.execute(
        select(func.count())
        .select_from(DuplicateCandidate)
        .where(DuplicateCandidate.status == "PENDING")
    ).scalar()
    transit_stops = session.execute(select(func.count()).select_from(TransitStop)).scalar()
    return {
        "active": listing_counts.get("ACTIVE", 0),
        "candidate": listing_counts.get("CANDIDATE", 0),
        "inactive": listing_counts.get("INACTIVE", 0),
        "review_required": listing_counts.get("REVIEW_REQUIRED", 0),
        "total": sum(listing_counts.values()),
        "selected": selected or 0,
        "open_issues": open_issues or 0,
        "pending_duplicates": pending_dups or 0,
        "transit_stops": transit_stops or 0,
    }


def freshness_buckets(session: Session) -> list[tuple[str, int]]:
    """Active-inventory last-seen ages for the dashboard freshness chart."""
    rows = session.execute(
        text(
            "SELECT CASE"
            " WHEN now() - last_seen_at <= interval '1 day' THEN '0-1d'"
            " WHEN now() - last_seen_at <= interval '3 days' THEN '1-3d'"
            " WHEN now() - last_seen_at <= interval '7 days' THEN '3-7d'"
            " ELSE '7d+' END AS bucket, count(*) AS n"
            " FROM app.canonical_listing"
            " WHERE lifecycle_status IN ('ACTIVE', 'CANDIDATE', 'REAPPEARED')"
            " GROUP BY 1"
        )
    ).all()
    counts = {bucket: n for bucket, n in rows}
    return [(bucket, counts.get(bucket, 0)) for bucket in ("0-1d", "1-3d", "3-7d", "7d+")]


def recent_refresh_runs(session: Session, limit: int = 8) -> list[dict[str, Any]]:
    rows = (
        session.execute(select(RefreshRun).order_by(RefreshRun.started_at.desc()).limit(limit))
        .scalars()
        .all()
    )
    return [
        {
            "run": run.logical_run_key,
            "trigger": run.trigger_type,
            "status": run.status,
            "started": run.started_at,
            "completed": run.completed_at,
        }
        for run in rows
    ]


def recent_events(session: Session, limit: int = 15) -> list[dict[str, Any]]:
    rows = (
        session.execute(select(ListingEvent).order_by(ListingEvent.recorded_at.desc()).limit(limit))
        .scalars()
        .all()
    )
    return [
        {
            "time": ev.event_time,
            "event": ev.event_type,
            "listing_id": str(ev.canonical_listing_id),
            "after": ev.after_values,
        }
        for ev in rows
    ]


# -- inventory -----------------------------------------------------------------


@dataclass
class InventoryFilters:
    layouts: list[str] | None = None
    lifecycle: list[str] | None = None
    laundry: list[str] | None = None
    max_rent_minor: int | None = None
    min_rent_minor: int | None = None
    locality: str | None = None
    selected_only: bool = False
    # Only listings with a known monthly rent (the map/inventory workspace
    # excludes rent-unknown listings by owner decision 2026-08-18).
    has_rent: bool = False
    # Only listings with a floor plan on file (listing- or building-level).
    has_floor_plan: bool = False
    # Spatial filters (08 §16.2): map bounds as (min_lon, min_lat, max_lon,
    # max_lat), or a drawn GeoJSON geometry (Polygon). Listings without
    # coordinates never match a spatial filter (no guessed placement).
    bounds: tuple[float, float, float, float] | None = None
    geometry_geojson: dict[str, Any] | None = None
    limit: int = 500


def inventory(session: Session, filters: InventoryFilters) -> list[dict[str, Any]]:
    """One filter contract used by map, table, and export alike (08 §16.2)."""
    lon_col = text("ST_X(app.address.location_point::geometry)")
    lat_col = text("ST_Y(app.address.location_point::geometry)")
    query = (
        select(
            CanonicalListing,
            Address,
            MarketingSelection.selection_status,
            lon_col,
            lat_col,
        )
        .join(Building, Building.building_id == CanonicalListing.building_id)
        .join(Address, Address.address_id == Building.address_id)
        .outerjoin(
            MarketingSelection,
            MarketingSelection.canonical_listing_id == CanonicalListing.canonical_listing_id,
        )
        .order_by(CanonicalListing.last_seen_at.desc())
        .limit(filters.limit)
    )
    if filters.layouts:
        query = query.where(CanonicalListing.layout_class.in_(filters.layouts))
    if filters.lifecycle:
        query = query.where(CanonicalListing.lifecycle_status.in_(filters.lifecycle))
    if filters.laundry:
        query = query.where(CanonicalListing.laundry_type.in_(filters.laundry))
    if filters.max_rent_minor:
        query = query.where(CanonicalListing.monthly_rent_minor <= filters.max_rent_minor)
    if filters.min_rent_minor:
        query = query.where(CanonicalListing.monthly_rent_minor >= filters.min_rent_minor)
    if filters.locality:
        query = query.where(Address.locality.ilike(f"%{filters.locality}%"))
    if filters.selected_only:
        query = query.where(MarketingSelection.selection_status == "SELECTED")
    if filters.has_rent:
        query = query.where(CanonicalListing.monthly_rent_minor.is_not(None))
    if filters.has_floor_plan:
        query = query.where(
            select(MediaAssociation.media_association_id)
            .join(MediaAsset, MediaAsset.media_asset_id == MediaAssociation.media_asset_id)
            .where(
                MediaAsset.media_type == "FLOOR_PLAN",
                (
                    MediaAssociation.canonical_listing_id
                    == CanonicalListing.canonical_listing_id
                )
                | (MediaAssociation.building_id == CanonicalListing.building_id),
            )
            .exists()
        )
    if filters.bounds is not None:
        min_lon, min_lat, max_lon, max_lat = filters.bounds
        query = query.where(
            text(
                "app.address.location_point IS NOT NULL AND ST_Intersects("
                "app.address.location_point::geometry, "
                "ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326))"
            ).bindparams(min_lon=min_lon, min_lat=min_lat, max_lon=max_lon, max_lat=max_lat)
        )
    if filters.geometry_geojson is not None:
        import json as _json

        query = query.where(
            text(
                "app.address.location_point IS NOT NULL AND ST_Intersects("
                "app.address.location_point::geometry, "
                "ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326))"
            ).bindparams(geojson=_json.dumps(filters.geometry_geojson))
        )

    results = []
    for listing, address, selection_status, lon, lat in session.execute(query):
        results.append(
            {
                "listing_id": str(listing.canonical_listing_id),
                "building_id": str(listing.building_id),
                "layout": listing.layout_class,
                "rent_minor": listing.monthly_rent_minor,
                "rent": (
                    f"${listing.monthly_rent_minor // 100:,}"
                    if listing.monthly_rent_minor is not None
                    else "unknown"
                ),
                "lifecycle": listing.lifecycle_status,
                "laundry": laundry_label(
                    listing.laundry_type, listing.indoor_laundry_badge_eligible
                ),
                "address": address.formatted_address,
                "locality": address.locality,
                "precision": address.location_precision,
                "lon": lon,
                "lat": lat,
                "selected": selection_status == "SELECTED",
                "first_seen": listing.first_seen_at,
                "last_seen": listing.last_seen_at,
            }
        )
    return results


# -- listing detail ------------------------------------------------------------


def listing_detail(session: Session, listing_id: uuid.UUID) -> dict[str, Any] | None:
    listing = session.get(CanonicalListing, listing_id)
    if listing is None:
        return None
    building = session.get(Building, listing.building_id)
    address = session.get(Address, building.address_id) if building else None
    links = session.execute(
        select(ListingSourceLink, Source.display_name)
        .join(Source, Source.source_id == ListingSourceLink.source_id)
        .where(ListingSourceLink.canonical_listing_id == listing_id)
    ).all()
    events = (
        session.execute(
            select(ListingEvent)
            .where(ListingEvent.canonical_listing_id == listing_id)
            .order_by(ListingEvent.event_time.desc())
        )
        .scalars()
        .all()
    )
    selection = session.execute(
        select(MarketingSelection).where(MarketingSelection.canonical_listing_id == listing_id)
    ).scalar_one_or_none()
    overrides = (
        session.execute(
            select(HumanOverride).where(
                HumanOverride.entity_id == listing_id,
                HumanOverride.override_status == "ACTIVE",
            )
        )
        .scalars()
        .all()
    )
    lon = lat = None
    if address is not None and address.location_point is not None:
        row = session.execute(
            text(
                "SELECT ST_X(location_point::geometry), ST_Y(location_point::geometry) "
                "FROM app.address WHERE address_id = :id"
            ),
            {"id": address.address_id},
        ).first()
        if row:
            lon, lat = row
    return {
        "listing": listing,
        "address": address,
        "lon": lon,
        "lat": lat,
        "links": [
            {
                "source": display_name,
                "url": link.source_url,
                "discovery": link.discovery_method,
                "identity": link.identity_method,
                "status": link.link_status,
                "last_seen": link.last_seen_at,
            }
            for link, display_name in links
        ],
        "events": events,
        "selection": selection,
        "overrides": overrides,
        "laundry_label": laundry_label(listing.laundry_type, listing.indoor_laundry_badge_eligible),
    }


def fact_history(session: Session, listing_id: uuid.UUID) -> dict[str, list[dict[str, Any]]]:
    """Evidence expander data: assertions per fact key, current one flagged."""
    current_ids = {
        row.effective_assertion_id
        for row in session.execute(
            select(FactResolution).where(
                FactResolution.entity_id == listing_id,
                FactResolution.superseded_at.is_(None),
            )
        ).scalars()
    }
    grouped: dict[str, list[dict[str, Any]]] = {}
    for assertion in session.execute(
        select(FactAssertion)
        .where(FactAssertion.entity_id == listing_id)
        .order_by(FactAssertion.asserted_at.desc())
    ).scalars():
        grouped.setdefault(assertion.fact_key, []).append(
            {
                "value": (assertion.value_json or {}).get("value"),
                "status": assertion.value_status,
                "derivation": assertion.derivation_type,
                "confidence": assertion.confidence,
                "evidence": assertion.evidence_text,
                "asserted_at": assertion.asserted_at,
                "current": assertion.fact_assertion_id in current_ids,
            }
        )
    return grouped


def commutes_for_listing(session: Session, listing_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = session.execute(
        select(CommuteResult, Destination)
        .join(Destination, Destination.destination_id == CommuteResult.destination_id)
        .where(CommuteResult.canonical_listing_id == listing_id)
        .order_by(Destination.destination_type, Destination.display_name)
    ).all()
    return [
        {
            "destination": destination.display_name,
            "type": destination.destination_type,
            "range_min": result.duration_min_s,
            "range_max": result.duration_max_s,
            "transfers": result.transfer_count,
            "confidence": result.confidence,
            "validation": result.validation_status,
            "validation_reasons": result.validation_reasons,
            "sources": result.sources or [],
            "summary": (result.route_summary or {}).get("summary"),
            "routes": (result.route_summary or {}).get("likely_routes"),
            "calculated_at": result.calculated_at,
            "expires_at": result.expires_at,
        }
        for result, destination in rows
    ]


def active_destinations(session: Session) -> list[Destination]:
    return list(
        session.execute(
            select(Destination)
            .where(Destination.active.is_(True))
            .order_by(Destination.destination_type, Destination.display_name)
        ).scalars()
    )


def transit_for_listing(session: Session, listing_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = session.execute(
        select(TransitAccess, TransitStop.stop_name, TransitStop.operator_code)
        .join(TransitStop, TransitStop.transit_stop_id == TransitAccess.transit_stop_id)
        .where(TransitAccess.canonical_listing_id == listing_id)
        .order_by(TransitAccess.mode, TransitAccess.proximity_rank)
    ).all()
    return [
        {
            "mode": access.mode,
            "stop": stop_name,
            "operator": operator,
            "straight_line_m": access.straight_line_distance_m,
            "walking_m": access.walking_distance_m,
            "walk_min": (
                round(access.walking_duration_s / 60)
                if access.walking_duration_s is not None
                else None
            ),
            "rank": access.proximity_rank,
            "usefulness": access.usefulness_status,
            "dataset": access.dataset_version,
        }
        for access, stop_name, operator in rows
    ]


def listings_in_building(session: Session, building_id: uuid.UUID) -> list[dict[str, Any]]:
    """Sibling units at the same property, for the unit-selection UI."""
    rows = session.execute(
        select(CanonicalListing)
        .where(CanonicalListing.building_id == building_id)
        .order_by(CanonicalListing.monthly_rent_minor.asc().nulls_last())
    ).scalars()
    return [
        {
            "listing_id": str(listing.canonical_listing_id),
            "layout": listing.layout_class,
            "rent_minor": listing.monthly_rent_minor,
            "rent": (
                f"${listing.monthly_rent_minor // 100:,}"
                if listing.monthly_rent_minor is not None
                else "unknown"
            ),
            "lifecycle": listing.lifecycle_status,
        }
        for listing in rows
    ]


def floor_plans_for_listing(
    session: Session, listing_id: uuid.UUID, building_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Floor-plan media for a listing (listing-level or building-level links)."""
    rows = session.execute(
        select(MediaAsset, MediaAssociation)
        .join(MediaAssociation, MediaAssociation.media_asset_id == MediaAsset.media_asset_id)
        .where(
            MediaAsset.media_type == "FLOOR_PLAN",
            (MediaAssociation.canonical_listing_id == listing_id)
            | (MediaAssociation.building_id == building_id),
        )
        .order_by(MediaAssociation.confidence.desc())
    ).all()
    return [
        {
            "url": asset.source_url,
            "storage_ref": asset.storage_ref,
            "availability": asset.availability_status,
            "level": association.association_level,
            "confidence": association.confidence,
        }
        for asset, association in rows
    ]


def laundry_counts(session: Session) -> dict[str, int]:
    """How many active-ish listings have confirmed in-unit / building laundry."""
    in_unit_types = (
        "IN_UNIT_WASHER_DRYER_CONFIRMED",
        "IN_UNIT_WASHER_ONLY",
        "IN_UNIT_DRYER_ONLY",
        "IN_UNIT_HOOKUP_ONLY",
    )
    rows = session.execute(
        select(CanonicalListing.laundry_type, func.count()).group_by(
            CanonicalListing.laundry_type
        )
    ).all()
    counts = {laundry_type: n for laundry_type, n in rows}
    return {
        "in_unit": sum(counts.get(t, 0) for t in in_unit_types),
        "building": counts.get("BUILDING_SHARED_LAUNDRY", 0),
    }


# -- review queue --------------------------------------------------------------


def open_review_issues(session: Session) -> list[dict[str, Any]]:
    rows = (
        session.execute(
            select(ReviewIssue)
            .where(ReviewIssue.status == "OPEN")
            .order_by(ReviewIssue.severity.desc(), ReviewIssue.created_at.asc())
        )
        .scalars()
        .all()
    )
    return [
        {
            "issue_id": str(issue.review_issue_id),
            "type": issue.issue_type,
            "severity": issue.severity,
            "entity_id": str(issue.entity_id),
            "created": issue.created_at,
            "details": issue.details,
        }
        for issue in rows
    ]


def pending_duplicate_candidates(session: Session) -> list[dict[str, Any]]:
    rows = (
        session.execute(select(DuplicateCandidate).where(DuplicateCandidate.status == "PENDING"))
        .scalars()
        .all()
    )
    return [
        {
            "candidate_id": str(candidate.duplicate_candidate_id),
            "listing_a": str(candidate.listing_a_id),
            "listing_b": str(candidate.listing_b_id),
            "evidence": candidate.evidence,
        }
        for candidate in rows
    ]


# -- selected / shortlists -----------------------------------------------------


def shortlist_presets(session: Session) -> list[ClientSearchPreset]:
    return list(
        session.execute(
            select(ClientSearchPreset)
            .where(ClientSearchPreset.archived_at.is_(None))
            .order_by(ClientSearchPreset.created_at)
        ).scalars()
    )


def shortlist_entries(session: Session, preset_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = session.execute(
        select(ClientShortlistEntry, CanonicalListing, Address)
        .join(
            CanonicalListing,
            CanonicalListing.canonical_listing_id == ClientShortlistEntry.canonical_listing_id,
        )
        .join(Building, Building.building_id == CanonicalListing.building_id)
        .join(Address, Address.address_id == Building.address_id)
        .where(ClientShortlistEntry.client_search_preset_id == preset_id)
    ).all()
    return [
        {
            "listing_id": str(listing.canonical_listing_id),
            "status": entry.entry_status,
            "address": address.formatted_address,
            "layout": listing.layout_class,
            "rent_minor": listing.monthly_rent_minor,
            "lifecycle": listing.lifecycle_status,
            "note": entry.note,
        }
        for entry, listing, address in rows
    ]


# -- operations ----------------------------------------------------------------


def source_run_history(session: Session, limit: int = 20) -> list[dict[str, Any]]:
    rows = session.execute(
        select(SourceRun, Source.source_code)
        .join(Source, Source.source_id == SourceRun.source_id)
        .order_by(SourceRun.started_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "source": code,
            "status": run.status,
            "health_gate": run.health_gate_passed,
            "started": run.started_at,
            "counts": run.counts,
        }
        for run, code in rows
    ]


def job_queue_summary(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(
        select(Job.job_type, Job.status, func.count()).group_by(Job.job_type, Job.status)
    ).all()
    return [{"job_type": t, "status": s, "count": c} for t, s, c in rows]
