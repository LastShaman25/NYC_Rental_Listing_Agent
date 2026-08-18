"""Manual merge/split workflow and duplicate-candidate resolution (02 §8.5, §9.4; 08 §11).

Human decisions on identity are durable: a confirmed-distinct pair is never
re-proposed under the same rule version, and a manual merge survives later
refreshes because the moved source links keep matching future observations to
the surviving listing. Merges never delete anything — the superseded listing
stays with lifecycle MERGED and a canonical_merge row records evidence and the
moved links so the operation can be reversed.

Manual actions require a HUMAN actor and are audited. Marketing selection and
shortlist state are never touched by a merge (owner invariant).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from rental_agent.canonical.selection_service import _require_human
from rental_agent.contracts import enums as e
from rental_agent.db.models import (
    AuditActionLog,
    CanonicalListing,
    CanonicalMerge,
    DuplicateCandidate,
    ListingEvent,
    ListingSourceLink,
    ReviewIssue,
)


class MergeError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(tz=UTC)


class MergeService:
    def __init__(self, session: Session) -> None:
        self._s = session

    # -- merge -----------------------------------------------------------------

    def merge_listings(
        self,
        *,
        source_listing_id: uuid.UUID,
        target_listing_id: uuid.UUID,
        actor: str,
        actor_type: e.ActorType,
        reason_code: e.MergeReasonCode = e.MergeReasonCode.MANUAL,
        evidence: dict | None = None,
    ) -> CanonicalMerge:
        """Merge source into target: links move, source becomes MERGED, history stays."""
        if reason_code is e.MergeReasonCode.MANUAL:
            _require_human(actor_type)
        if source_listing_id == target_listing_id:
            raise MergeError("cannot merge a listing into itself")
        source = self._s.get(CanonicalListing, source_listing_id)
        target = self._s.get(CanonicalListing, target_listing_id)
        if source is None or target is None:
            raise LookupError("source or target listing not found")
        if source.lifecycle_status == e.LifecycleStatus.MERGED.value:
            raise MergeError("source listing is already merged")
        if target.lifecycle_status == e.LifecycleStatus.MERGED.value:
            raise MergeError("target listing is itself merged; merge into its survivor")

        moved_link_ids = [
            str(link_id)
            for link_id in self._s.execute(
                select(ListingSourceLink.listing_source_link_id).where(
                    ListingSourceLink.canonical_listing_id == source_listing_id
                )
            ).scalars()
        ]
        self._s.execute(
            update(ListingSourceLink)
            .where(ListingSourceLink.canonical_listing_id == source_listing_id)
            .values(canonical_listing_id=target_listing_id)
        )

        now = _now()
        merge = CanonicalMerge(
            source_listing_id=source_listing_id,
            target_listing_id=target_listing_id,
            reason_code=reason_code.value,
            evidence={**(evidence or {}), "moved_link_ids": moved_link_ids},
            performed_by_type=(
                e.PerformedByType.HUMAN.value
                if actor_type is e.ActorType.HUMAN
                else e.PerformedByType.SYSTEM.value
            ),
            performed_by=actor,
            performed_at=now,
        )
        self._s.add(merge)
        source.lifecycle_status = e.LifecycleStatus.MERGED.value
        target.last_seen_at = max(target.last_seen_at, source.last_seen_at)
        self._emit_event(
            source_listing_id,
            e.ListingEventType.MERGED,
            key=f"{source_listing_id}:MERGED:{target_listing_id}",
            after_values={"target_listing_id": str(target_listing_id)},
        )
        self._s.add(
            AuditActionLog(
                actor=actor,
                actor_type=actor_type.value,
                action_type="canonical_merge",
                target_type="canonical_listing",
                target_id=source_listing_id,
                after_values={
                    "target_listing_id": str(target_listing_id),
                    "reason_code": reason_code.value,
                },
            )
        )
        self._s.flush()
        return merge

    def reverse_merge(
        self,
        canonical_merge_id: uuid.UUID,
        *,
        actor: str,
        actor_type: e.ActorType,
        reason: str,
    ) -> None:
        """Undo a merge: moved links return; the superseded listing needs review."""
        _require_human(actor_type)
        merge = self._s.get(CanonicalMerge, canonical_merge_id)
        if merge is None:
            raise LookupError("merge record not found")
        if merge.reversed_at is not None:
            raise MergeError("merge already reversed")
        moved = [uuid.UUID(link_id) for link_id in merge.evidence.get("moved_link_ids", [])]
        if moved:
            self._s.execute(
                update(ListingSourceLink)
                .where(ListingSourceLink.listing_source_link_id.in_(moved))
                .values(canonical_listing_id=merge.source_listing_id)
            )
        source = self._s.get(CanonicalListing, merge.source_listing_id)
        assert source is not None
        # Reversal does not guess the correct lifecycle; a human review decides.
        source.lifecycle_status = e.LifecycleStatus.REVIEW_REQUIRED.value
        merge.reversed_at = _now()
        self._s.add(
            AuditActionLog(
                actor=actor,
                actor_type=actor_type.value,
                action_type="canonical_merge_reversed",
                target_type="canonical_listing",
                target_id=merge.source_listing_id,
                reason=reason,
            )
        )
        self._s.flush()

    # -- duplicate-candidate resolution ---------------------------------------

    def resolve_duplicate_candidate(
        self,
        duplicate_candidate_id: uuid.UUID,
        *,
        confirmed_duplicate: bool,
        actor: str,
        actor_type: e.ActorType,
        survivor_listing_id: uuid.UUID | None = None,
    ) -> DuplicateCandidate:
        """Human verdict on a candidate pair. Confirmed duplicates merge into the
        chosen survivor; confirmed-distinct is durable (PR-ACQ-004)."""
        _require_human(actor_type)
        candidate = self._s.get(DuplicateCandidate, duplicate_candidate_id)
        if candidate is None:
            raise LookupError("duplicate candidate not found")
        if candidate.status != e.DuplicateCandidateStatus.PENDING.value:
            raise MergeError(f"candidate already resolved: {candidate.status}")

        if confirmed_duplicate:
            survivor = survivor_listing_id or candidate.listing_a_id
            if survivor not in (candidate.listing_a_id, candidate.listing_b_id):
                raise MergeError("survivor must be one of the candidate pair")
            merged_away = (
                candidate.listing_b_id
                if survivor == candidate.listing_a_id
                else candidate.listing_a_id
            )
            self.merge_listings(
                source_listing_id=merged_away,
                target_listing_id=survivor,
                actor=actor,
                actor_type=actor_type,
                reason_code=e.MergeReasonCode.MANUAL,
                evidence={"duplicate_candidate_id": str(duplicate_candidate_id)},
            )
            candidate.status = e.DuplicateCandidateStatus.CONFIRMED_DUPLICATE.value
        else:
            candidate.status = e.DuplicateCandidateStatus.CONFIRMED_DISTINCT.value
        candidate.resolved_by = actor
        candidate.resolved_at = _now()
        self._resolve_candidate_issues(duplicate_candidate_id, actor)
        self._s.flush()
        return candidate

    # -- helpers ---------------------------------------------------------------

    def _emit_event(
        self,
        canonical_listing_id: uuid.UUID,
        event_type: e.ListingEventType,
        *,
        key: str,
        after_values: dict | None = None,
    ) -> None:
        self._s.execute(
            pg_insert(ListingEvent)
            .values(
                canonical_listing_id=canonical_listing_id,
                event_type=event_type.value,
                event_time=_now(),
                after_values=after_values,
                idempotency_key=key,
            )
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
        )

    def _resolve_candidate_issues(self, duplicate_candidate_id: uuid.UUID, actor: str) -> None:
        issues = (
            self._s.execute(
                select(ReviewIssue).where(
                    ReviewIssue.issue_type == e.ReviewIssueType.DUPLICATE_CANDIDATE.value,
                    ReviewIssue.status == e.ReviewIssueStatus.OPEN.value,
                )
            )
            .scalars()
            .all()
        )
        for issue in issues:
            if issue.details.get("duplicate_candidate_id") == str(duplicate_candidate_id):
                issue.status = e.ReviewIssueStatus.RESOLVED.value
                issue.resolved_at = _now()
                issue.resolved_by = actor
