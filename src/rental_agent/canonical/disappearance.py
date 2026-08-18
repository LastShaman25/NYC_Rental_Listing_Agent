"""Disappearance and inactivation processing (06 §16, §24.4).

Absence is evidence only inside a HEALTHY, gate-passed source run — search-
index runs never pass the gate (B3), so this service structurally cannot
inactivate search-discovered inventory. Rules:

- Link ACTIVE → MISSING: absent from one gate-passed run.
- Link MISSING → REMOVED: absent from ≥2 consecutive gate-passed scheduled runs
  AND ≥36h since last healthy observation (initial defaults, 06 §16.4).
- Listing → INACTIVE only when NO supporting link remains active/missing, no
  active lifecycle override exists, and the mass-inactivation circuit breaker
  stays closed. Everything is evented and reversible (REAPPEARED path exists in
  normalization via link continuity).

Circuit breaker (06 §24.4): if proposed inactivations exceed the absolute cap
or the percentage of currently active inventory, NOTHING is applied; a BLOCKING
review issue records the proposal for diagnosis.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from rental_agent.config.logging import get_logger
from rental_agent.contracts import enums as e
from rental_agent.db.models import (
    CanonicalListing,
    HumanOverride,
    ListingEvent,
    ListingSourceLink,
    ReviewIssue,
    SourceObservation,
    SourceRun,
)

log = get_logger(__name__)

REMOVAL_CONSECUTIVE_MISSES = 2
REMOVAL_MIN_ELAPSED = timedelta(hours=36)
# Circuit breaker (initial defaults; calibration inputs, 06 §24.4).
BREAKER_ABSOLUTE_MAX = 50
BREAKER_MAX_FRACTION_OF_ACTIVE = 0.25
RULE_VERSION = "disappearance-v1"


@dataclass
class DisappearanceSummary:
    refused_reason: str | None = None
    links_marked_missing: int = 0
    links_removed: int = 0
    listings_inactivated: int = 0
    breaker_tripped: bool = False
    proposed_inactivations: int = 0
    details: dict = field(default_factory=dict)


class DisappearanceService:
    def __init__(self, session: Session) -> None:
        self._s = session

    def process_source_run(self, source_run_id: uuid.UUID) -> DisappearanceSummary:
        summary = DisappearanceSummary()
        run = self._s.get(SourceRun, source_run_id)
        if run is None:
            raise LookupError("source run not found")
        # Safety default: unknown health is not healthy (06 §17.4).
        if run.health_gate_passed is not True:
            summary.refused_reason = "health_gate_not_passed"
            log.info("disappearance_refused", source_run_id=str(source_run_id))
            return summary

        observed_link_ids = set(
            self._s.execute(
                select(ListingSourceLink.listing_source_link_id)
                .join(
                    SourceObservation,
                    SourceObservation.source_observation_id
                    == ListingSourceLink.latest_observation_id,
                )
                .where(SourceObservation.source_run_id == source_run_id)
            ).scalars()
        )
        now = datetime.now(tz=UTC)
        links = (
            self._s.execute(
                select(ListingSourceLink).where(
                    ListingSourceLink.source_id == run.source_id,
                    ListingSourceLink.link_status.in_(
                        [e.LinkStatus.ACTIVE.value, e.LinkStatus.MISSING.value]
                    ),
                )
            )
            .scalars()
            .all()
        )
        for link in links:
            if link.listing_source_link_id in observed_link_ids:
                if link.link_status == e.LinkStatus.MISSING.value:
                    link.link_status = e.LinkStatus.ACTIVE.value  # reappeared in-source
                continue
            healthy_misses = self._healthy_runs_since(run.source_id, link.last_seen_at)
            if (
                healthy_misses >= REMOVAL_CONSECUTIVE_MISSES
                and now - link.last_seen_at >= REMOVAL_MIN_ELAPSED
            ):
                link.link_status = e.LinkStatus.REMOVED.value
                summary.links_removed += 1
            elif link.link_status == e.LinkStatus.ACTIVE.value:
                link.link_status = e.LinkStatus.MISSING.value
                summary.links_marked_missing += 1
                self._emit(
                    link.canonical_listing_id,
                    e.ListingEventType.MISSING_STARTED,
                    now,
                    key_suffix=str(source_run_id),
                )
        self._s.flush()
        self._inactivate_unsupported(summary, now)
        log.info(
            "disappearance_run",
            source_run_id=str(source_run_id),
            missing=summary.links_marked_missing,
            removed=summary.links_removed,
            inactivated=summary.listings_inactivated,
            breaker=summary.breaker_tripped,
        )
        return summary

    def _healthy_runs_since(self, source_id: uuid.UUID, since: datetime) -> int:
        return self._s.execute(
            select(func.count())
            .select_from(SourceRun)
            .where(
                SourceRun.source_id == source_id,
                SourceRun.health_gate_passed.is_(True),
                SourceRun.started_at > since,
            )
        ).scalar_one()

    def _inactivate_unsupported(self, summary: DisappearanceSummary, now: datetime) -> None:
        # Listings whose every link is REMOVED/SUPERSEDED and that are not merged.
        supported = (
            select(ListingSourceLink.listing_source_link_id)
            .where(
                ListingSourceLink.canonical_listing_id == CanonicalListing.canonical_listing_id,
                ListingSourceLink.link_status.in_(
                    [
                        e.LinkStatus.ACTIVE.value,
                        e.LinkStatus.MISSING.value,
                        e.LinkStatus.CONFLICTING.value,
                    ]
                ),
            )
            .exists()
        )
        candidates = (
            self._s.execute(
                select(CanonicalListing).where(
                    CanonicalListing.lifecycle_status.in_(
                        [e.LifecycleStatus.ACTIVE.value, e.LifecycleStatus.CANDIDATE.value]
                    ),
                    ~supported,
                )
            )
            .scalars()
            .all()
        )
        # Respect active lifecycle overrides (06 §16.5).
        eligible = [
            listing
            for listing in candidates
            if self._s.execute(
                select(HumanOverride.human_override_id)
                .where(
                    HumanOverride.entity_id == listing.canonical_listing_id,
                    HumanOverride.field_name == "lifecycle_status",
                    HumanOverride.override_status == e.OverrideStatus.ACTIVE.value,
                )
                .limit(1)
            ).scalar_one_or_none()
            is None
        ]
        summary.proposed_inactivations = len(eligible)
        if not eligible:
            return

        active_count = self._s.execute(
            select(func.count())
            .select_from(CanonicalListing)
            .where(CanonicalListing.lifecycle_status == e.LifecycleStatus.ACTIVE.value)
        ).scalar_one()
        cap = min(
            BREAKER_ABSOLUTE_MAX,
            max(1, int(active_count * BREAKER_MAX_FRACTION_OF_ACTIVE)),
        )
        if len(eligible) > cap:
            summary.breaker_tripped = True
            summary.details = {"proposed": len(eligible), "cap": cap, "active": active_count}
            self._s.add(
                ReviewIssue(
                    entity_type=e.FactEntityType.LISTING.value,
                    entity_id=eligible[0].canonical_listing_id,
                    issue_type=e.ReviewIssueType.SOURCE_FAILURE.value,
                    severity=e.ReviewIssueSeverity.BLOCKING.value,
                    details={
                        "rule": RULE_VERSION,
                        "reason": "mass_inactivation_circuit_breaker",
                        "proposed_inactivations": len(eligible),
                        "cap": cap,
                        "listing_ids": [str(x.canonical_listing_id) for x in eligible[:100]],
                    },
                )
            )
            log.error("mass_inactivation_blocked", proposed=len(eligible), cap=cap)
            return

        for listing in eligible:
            listing.lifecycle_status = e.LifecycleStatus.INACTIVE.value
            listing.inactive_at = now
            self._emit(
                listing.canonical_listing_id,
                e.ListingEventType.INACTIVATED,
                now,
                key_suffix=RULE_VERSION,
            )
            summary.listings_inactivated += 1
        self._s.flush()

    def _emit(
        self,
        listing_id: uuid.UUID,
        event_type: e.ListingEventType,
        now: datetime,
        *,
        key_suffix: str,
    ) -> None:
        self._s.execute(
            pg_insert(ListingEvent)
            .values(
                canonical_listing_id=listing_id,
                event_type=event_type.value,
                event_time=now,
                after_values={"rule": RULE_VERSION},
                idempotency_key=f"{listing_id}:{event_type.value}:{key_suffix}",
            )
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
        )
