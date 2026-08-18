"""Listing admission: CANDIDATE → ACTIVE / EXCLUDED (02 §22.1).

A listing becomes ACTIVE only when every check passes:
- layout is STUDIO / ONE_BEDROOM / TWO_BEDROOM;
- geography is IN_SCOPE at acceptable precision (rooftop/building/parcel/
  interpolated — 04 §8.4);
- canonical identity is at least provisional without a blocking conflict;
- at least one ACTIVE source link supports it.

Layout OUT_OF_SCOPE or geography OUT_OF_SCOPE → EXCLUDED (with event).
Everything else stays CANDIDATE — unknowns are never admitted optimistically.
Full enrichment is NOT required for activation (02 §22.1). Admission never
touches selection/shortlist state and never inactivates (disappearance rules
are separate and gated).
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from rental_agent.config.logging import get_logger
from rental_agent.contracts import enums as e
from rental_agent.db.models import (
    Address,
    Building,
    CanonicalListing,
    ListingEvent,
    ListingSourceLink,
)

log = get_logger(__name__)

ADMISSIBLE_LAYOUTS = {"STUDIO", "ONE_BEDROOM", "TWO_BEDROOM"}
ACCEPTABLE_PRECISION = {
    "ROOFTOP_OR_ENTRANCE",
    "BUILDING",
    "PARCEL",
    "INTERPOLATED_ADDRESS",
}
BLOCKING_RESOLUTION = {"CONFLICTING", "REVIEW_REQUIRED"}
ADMISSION_RULE_VERSION = "admission-v1"


@dataclass
class AdmissionSummary:
    evaluated: int = 0
    activated: int = 0
    excluded: int = 0
    still_candidate: int = 0
    reasons_held: dict[str, int] = field(default_factory=dict)


class AdmissionService:
    def __init__(self, session: Session) -> None:
        self._s = session

    def evaluate_candidates(self, limit: int = 1000) -> AdmissionSummary:
        summary = AdmissionSummary()
        rows = self._s.execute(
            select(CanonicalListing, Address)
            .join(Building, Building.building_id == CanonicalListing.building_id)
            .join(Address, Address.address_id == Building.address_id)
            .where(
                CanonicalListing.lifecycle_status.in_(
                    [e.LifecycleStatus.CANDIDATE.value, e.LifecycleStatus.REAPPEARED.value]
                )
            )
            .limit(limit)
        ).all()
        for listing, address in rows:
            summary.evaluated += 1
            outcome = self._evaluate_one(listing, address)
            if outcome == "ACTIVATED":
                summary.activated += 1
            elif outcome == "EXCLUDED":
                summary.excluded += 1
            else:
                summary.still_candidate += 1
                summary.reasons_held[outcome] = summary.reasons_held.get(outcome, 0) + 1
        log.info(
            "admission_run",
            evaluated=summary.evaluated,
            activated=summary.activated,
            excluded=summary.excluded,
            held=summary.still_candidate,
        )
        return summary

    def _evaluate_one(self, listing: CanonicalListing, address: Address) -> str:
        now = datetime.now(tz=UTC)

        # Hard exclusions first (02 §8.3): confirmed out-of-scope layout/geography.
        if listing.layout_class == e.LayoutClass.OUT_OF_SCOPE.value or (
            address.boundary_status == e.BoundaryStatus.OUT_OF_SCOPE.value
        ):
            reason = (
                "layout_out_of_scope"
                if listing.layout_class == e.LayoutClass.OUT_OF_SCOPE.value
                else "geography_out_of_scope"
            )
            listing.lifecycle_status = e.LifecycleStatus.EXCLUDED.value
            self._emit(listing.canonical_listing_id, e.ListingEventType.EXCLUDED, now, reason)
            return "EXCLUDED"

        # Holds: unknowns stay CANDIDATE, never admitted optimistically.
        if listing.layout_class not in ADMISSIBLE_LAYOUTS:
            return "layout_unresolved"
        if address.boundary_status != e.BoundaryStatus.IN_SCOPE.value:
            return "geography_unresolved"
        if address.location_precision not in ACCEPTABLE_PRECISION:
            return "precision_insufficient"
        if listing.canonical_resolution_status in BLOCKING_RESOLUTION:
            return "identity_blocked"
        has_active_link = (
            self._s.execute(
                select(ListingSourceLink.listing_source_link_id)
                .where(
                    ListingSourceLink.canonical_listing_id == listing.canonical_listing_id,
                    ListingSourceLink.link_status == e.LinkStatus.ACTIVE.value,
                )
                .limit(1)
            ).scalar_one_or_none()
            is not None
        )
        if not has_active_link:
            return "no_active_source_link"

        listing.lifecycle_status = e.LifecycleStatus.ACTIVE.value
        self._emit(listing.canonical_listing_id, e.ListingEventType.ACTIVATED, now, None)
        return "ACTIVATED"

    def _emit(
        self, listing_id: uuid.UUID, event_type: e.ListingEventType, now: datetime, reason
    ) -> None:
        self._s.execute(
            pg_insert(ListingEvent)
            .values(
                canonical_listing_id=listing_id,
                event_type=event_type.value,
                event_time=now,
                after_values={"rule": ADMISSION_RULE_VERSION, "reason": reason},
                idempotency_key=f"{listing_id}:{event_type.value}:{ADMISSION_RULE_VERSION}",
            )
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
        )
