"""Evidence-backed fact recording and override precedence (02 §10, §18).

Every important normalized value gets a ``fact_assertion`` (what the evidence
said, with provenance) and exactly one current ``fact_resolution`` (which
assertion is effective now). Materialized columns on canonical_listing remain
the fast query path; the resolution chain is the audit source (02 §10.2).

Override precedence (02 §18.2): an ACTIVE human override outranks every source
assertion. New conflicting evidence never overwrites the override — it is
recorded as an assertion and, when the override asks for it, surfaces as a
CONFLICT review issue for the operator.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from rental_agent.contracts import enums as e
from rental_agent.db.models import FactAssertion, FactResolution, HumanOverride, ReviewIssue

RESOLUTION_RULE_VERSION = "recency-1"


def _now() -> datetime:
    return datetime.now(tz=UTC)


class FactRecorder:
    def __init__(self, session: Session) -> None:
        self._s = session

    def record(
        self,
        *,
        entity_type: e.FactEntityType,
        entity_id: uuid.UUID,
        fact_key: str,
        value_json: dict[str, Any] | None,
        value_status: e.ValueStatus,
        derivation_type: e.DerivationType,
        confidence: e.Confidence,
        source_observation_id: uuid.UUID | None = None,
        evidence_text: str | None = None,
    ) -> FactAssertion:
        """Insert an assertion and make it the single current resolution.

        The previous current resolution (if any) is superseded, never deleted;
        an active human override keeps MANUAL_OVERRIDE resolution in place and
        the new assertion is recorded as evidence only.
        """
        assertion = FactAssertion(
            entity_type=entity_type.value,
            entity_id=entity_id,
            fact_key=fact_key,
            value_json=value_json,
            value_status=value_status.value,
            derivation_type=derivation_type.value,
            confidence=confidence.value,
            source_observation_id=source_observation_id,
            evidence_text=evidence_text,
        )
        self._s.add(assertion)
        self._s.flush()

        if self.active_override(entity_type, entity_id, fact_key) is not None:
            # Override stays effective (02 §18.2); evidence retained above.
            return assertion

        now = _now()
        self._s.execute(
            update(FactResolution)
            .where(
                FactResolution.entity_type == entity_type.value,
                FactResolution.entity_id == entity_id,
                FactResolution.fact_key == fact_key,
                FactResolution.superseded_at.is_(None),
            )
            .values(superseded_at=now)
        )
        resolution_status = (
            e.ResolutionStatus.RESOLVED
            if value_status is e.ValueStatus.ASSERTED
            else e.ResolutionStatus.UNKNOWN
        )
        self._s.add(
            FactResolution(
                entity_type=entity_type.value,
                entity_id=entity_id,
                fact_key=fact_key,
                effective_assertion_id=assertion.fact_assertion_id,
                resolution_status=resolution_status.value,
                resolution_method=e.ResolutionMethod.RECENCY.value,
                resolution_rule_version=RESOLUTION_RULE_VERSION,
            )
        )
        self._s.flush()
        return assertion

    def active_override(
        self, entity_type: e.FactEntityType, entity_id: uuid.UUID, field_name: str
    ) -> HumanOverride | None:
        return self._s.execute(
            select(HumanOverride).where(
                HumanOverride.entity_type == entity_type.value,
                HumanOverride.entity_id == entity_id,
                HumanOverride.field_name == field_name,
                HumanOverride.override_status == e.OverrideStatus.ACTIVE.value,
            )
        ).scalar_one_or_none()

    def raise_conflict_with_override(
        self,
        override: HumanOverride,
        *,
        entity_id: uuid.UUID,
        fact_key: str,
        incoming_value: Any,
    ) -> None:
        """New evidence disagrees with an active override: open ONE review issue
        (deduped while open) so the operator decides (02 §18.2)."""
        if not override.review_on_new_conflict:
            return
        open_issues = (
            self._s.execute(
                select(ReviewIssue).where(
                    ReviewIssue.entity_type == e.FactEntityType.LISTING.value,
                    ReviewIssue.entity_id == entity_id,
                    ReviewIssue.issue_type == e.ReviewIssueType.CONFLICT.value,
                    ReviewIssue.status == e.ReviewIssueStatus.OPEN.value,
                )
            )
            .scalars()
            .all()
        )
        for issue in open_issues:
            if issue.details.get("fact_key") == fact_key:
                return  # already surfaced
        self._s.add(
            ReviewIssue(
                entity_type=e.FactEntityType.LISTING.value,
                entity_id=entity_id,
                issue_type=e.ReviewIssueType.CONFLICT.value,
                severity=e.ReviewIssueSeverity.WARNING.value,
                details={
                    "fact_key": fact_key,
                    "override_id": str(override.human_override_id),
                    "override_value": override.override_value,
                    "incoming_value": incoming_value,
                    "reason": "new source evidence conflicts with active human override",
                },
            )
        )
