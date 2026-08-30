"""On-demand commute research service (04 §19A, owner decision B7).

The default hosted model (Terra) researches commute-time ranges with approved
web-search tools. Results persist as ``RESEARCHED_ESTIMATE`` commute rows with
sources, timestamp, confidence, and validation — never as authoritative routes.
Hard rules enforced here:

- Commute times never come from model memory: output without cited web sources
  is rejected outright.
- Research runs on demand (shortlisted / selected / explicitly requested
  listings); nothing in this module is called by bulk refresh enrichment.
- Named routes/stations are cross-checked against local transit data when
  loaded; otherwise validation records UNABLE_TO_VALIDATE.
- Results expire after the configured cache window (default 14 days).
"""

import hashlib
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from rental_agent.contracts import enums as e
from rental_agent.contracts.providers import LlmExecutor, LlmTaskRequest
from rental_agent.db.models import (
    CommuteResult,
    Destination,
    ModelExecution,
    TransitRoute,
    TransitStop,
)

TASK_TYPE = "commute_research"
PROMPT_VERSION = "1.0.0"
OUTPUT_SCHEMA_VERSION = "1.0.0"


class ResearchSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str
    title: str | None = None
    accessed_at: datetime | None = None


class CommuteResearchOutput(BaseModel):
    """Schema-constrained Terra output for one listing/destination pair."""

    model_config = ConfigDict(extra="forbid")
    duration_min_s: int = Field(ge=0)
    duration_max_s: int = Field(ge=0)
    likely_routes: list[str] = Field(
        default_factory=list,
        description=(
            "Short transit route labels only, one per entry — e.g. '1', 'A', "
            "'Q36', 'M60-SBS', 'PATH JSQ-33', 'LIRR Hempstead Branch'. "
            "No sentences; put narrative in summary."
        ),
    )
    transfer_count: int | None = Field(default=None, ge=0)
    named_stations: list[str] = Field(default_factory=list)
    summary: str | None = None
    sources: list[ResearchSource]  # REQUIRED — memory-only answers are invalid
    confidence: e.Confidence = e.Confidence.UNKNOWN


class CommuteResearchRejected(ValueError):
    """Raised when research output violates the no-memory/sources contract."""


class CommuteResearchService:
    def __init__(
        self,
        session: Session,
        llm: LlmExecutor,
        *,
        cache_days: int = 14,
    ) -> None:
        self._s = session
        self._llm = llm
        self._cache_days = cache_days

    def get_fresh_result(
        self,
        canonical_listing_id: uuid.UUID | None,
        destination_id: uuid.UUID,
        company_property_id: uuid.UUID | None = None,
    ) -> CommuteResult | None:
        """Return an unexpired researched estimate if one exists (14-day cache)."""
        now = datetime.now(tz=UTC)
        target_filter = (
            CommuteResult.canonical_listing_id == canonical_listing_id
            if canonical_listing_id is not None
            else CommuteResult.company_property_id == company_property_id
        )
        return self._s.execute(
            select(CommuteResult)
            .where(
                target_filter,
                CommuteResult.destination_id == destination_id,
                CommuteResult.result_type == e.CommuteResultType.RESEARCHED_ESTIMATE.value,
                CommuteResult.expires_at > now,
            )
            .order_by(CommuteResult.calculated_at.desc())
            .limit(1)
        ).scalar_one_or_none()

    def research(
        self,
        *,
        canonical_listing_id: uuid.UUID | None = None,
        company_property_id: uuid.UUID | None = None,
        destination_id: uuid.UUID,
        origin_description: str,
        input_location_hash: str,
    ) -> CommuteResult:
        """Run one on-demand research task and persist the estimate.

        Targets exactly one of a canonical listing or a company portfolio
        property (owner request 2026-08-30 — company checks research
        commutes too). The LLM call itself happens outside any open write
        transaction; this method only persists results (06 §13.3 — caller
        controls commit).
        """
        if (canonical_listing_id is None) == (company_property_id is None):
            raise ValueError(
                "research targets exactly one of "
                "canonical_listing_id / company_property_id"
            )
        cached = self.get_fresh_result(
            canonical_listing_id, destination_id, company_property_id
        )
        if cached is not None:
            return cached

        destination = self._s.get(Destination, destination_id)
        if destination is None:
            raise LookupError(f"destination {destination_id} not found")
        target_id = canonical_listing_id if canonical_listing_id is not None else (
            company_property_id
        )
        target_key = "listing" if canonical_listing_id is not None else "company_property"

        now = datetime.now(tz=UTC)
        input_payload = {
            "origin": origin_description,
            "destination": destination.display_name,
            "destination_anchor": destination.routing_anchor_name,
            "scenario": "typical weekday morning public-transit commute",
            "instructions": (
                "Use web search/browsing tools to research the typical public-transit "
                "commute-time range, likely routes, and transfers. Cite every source. "
                "Do not answer from memory."
            ),
        }
        input_hash = hashlib.sha256(
            repr(
                (
                    target_id,
                    destination.destination_code,
                    input_location_hash,
                    destination.registry_version,
                    PROMPT_VERSION,
                )
            ).encode()
        ).hexdigest()

        result = self._llm.execute(
            LlmTaskRequest(
                task_type=TASK_TYPE,
                prompt_version=PROMPT_VERSION,
                output_schema_version=OUTPUT_SCHEMA_VERSION,
                input_refs={
                    target_key: str(target_id),
                    "destination": destination.destination_code,
                },
                input_payload=input_payload,
                output_schema=CommuteResearchOutput.model_json_schema(),
                tier=e.ModelTier.DEFAULT_HOSTED,
            )
        )
        if result.status is not e.ModelExecutionStatus.SUCCEEDED or result.output is None:
            raise CommuteResearchRejected(f"research execution failed: {result.error_code}")

        try:
            output = CommuteResearchOutput.model_validate(result.output)
        except ValidationError as exc:
            raise CommuteResearchRejected(f"output failed schema validation: {exc}") from exc
        if not output.sources:
            raise CommuteResearchRejected("research output cited no web sources (memory-only)")
        if output.duration_min_s > output.duration_max_s:
            raise CommuteResearchRejected("duration range inverted")

        validation_status, validation_reasons = self._cross_check(output)

        execution = ModelExecution(
            provider_code=getattr(self._llm, "provider_code", "unknown"),
            model_id=result.model_id or "unknown",
            model_tier=e.ModelTier.DEFAULT_HOSTED.value,
            task_type=TASK_TYPE,
            prompt_version=PROMPT_VERSION,
            output_schema_version=OUTPUT_SCHEMA_VERSION,
            input_hash=input_hash,
            input_refs={
                target_key: str(target_id),
                "destination": destination.destination_code,
            },
            output_ref=output.model_dump(mode="json"),
            confidence=output.confidence.value,
            validation_status=e.ValidationStatus.PASSED.value
            if validation_status is e.TransitValidationStatus.PASSED
            else e.ValidationStatus.WARNING.value,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            started_at=now,
            completed_at=now,
            status=e.ModelExecutionStatus.SUCCEEDED.value,
        )
        self._s.add(execution)
        self._s.flush()

        commute = CommuteResult(
            canonical_listing_id=canonical_listing_id,
            company_property_id=company_property_id,
            destination_id=destination_id,
            result_type=e.CommuteResultType.RESEARCHED_ESTIMATE.value,
            model_execution_id=execution.model_execution_id,
            travel_mode=e.TravelMode.PUBLIC_TRANSIT.value,
            time_basis=e.TimeBasis.DEPART_AT.value,
            duration_min_s=output.duration_min_s,
            duration_max_s=output.duration_max_s,
            transfer_count=output.transfer_count,
            route_summary={
                "likely_routes": output.likely_routes,
                "named_stations": output.named_stations,
                "summary": output.summary,
                "label": "web-researched estimate",
            },
            sources=[s.model_dump(mode="json") for s in output.sources],
            confidence=output.confidence.value,
            result_status=e.CommuteResultStatus.AVAILABLE.value,
            validation_status=validation_status.value,
            validation_reasons=validation_reasons,
            input_location_hash=input_location_hash,
            destination_registry_version=destination.registry_version,
            calculated_at=now,
            expires_at=now + timedelta(days=self._cache_days),
        )
        self._s.add(commute)
        self._s.flush()
        return commute

    def _cross_check(
        self, output: CommuteResearchOutput
    ) -> tuple[e.TransitValidationStatus, dict[str, Any]]:
        """Cross-check named routes/stations against local transit data (04 §19A.5)."""
        dataset_rows = self._s.execute(select(func.count()).select_from(TransitStop)).scalar()
        if not dataset_rows:
            return (
                e.TransitValidationStatus.UNABLE_TO_VALIDATE,
                {"reason": "no local transit dataset loaded"},
            )
        unmatched: list[str] = []
        for station in output.named_stations:
            found = self._s.execute(
                select(TransitStop.transit_stop_id)
                .where(TransitStop.stop_name.ilike(f"%{station}%"))
                .limit(1)
            ).scalar_one_or_none()
            if found is None:
                unmatched.append(station)
        unmatched_routes: list[str] = []
        for route in output.likely_routes:
            # Route labels may arrive embedded in prose ("take an uptown 1 train",
            # "Q36 toward Jamaica"): extract short route-shaped tokens and match
            # any of them against loaded route short names.
            tokens = {t.upper() for t in re.split(r"[^A-Za-z0-9-]+", route) if t and len(t) <= 7}
            found = None
            if tokens:
                found = self._s.execute(
                    select(TransitRoute.transit_route_id)
                    .where(func.upper(TransitRoute.route_short_name).in_(tokens))
                    .limit(1)
                ).scalar_one_or_none()
            if found is None:
                unmatched_routes.append(route)
        if unmatched or unmatched_routes:
            return (
                e.TransitValidationStatus.WARNING,
                {"unmatched_stations": unmatched, "unmatched_routes": unmatched_routes},
            )
        return (e.TransitValidationStatus.PASSED, {})
