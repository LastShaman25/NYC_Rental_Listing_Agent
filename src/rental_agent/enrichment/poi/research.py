"""Nearby dining/store research for post writing (owner decision 2026-08-18).

The Studio's post rules mention nearby dining categories and named stores —
facts our listing data never contains, which the local model was hallucinating.
This service researches them with the hosted web-research executor (Google
Maps results and neighborhood sources on the live web — the same posture as
commute research: sources required, model memory forbidden), and caches the
result as a listing fact for 30 days.

Content rules mirror the owner's posting prompt: dining as CATEGORIES only
(no restaurant names); supermarkets/retail may be NAMED. Anything the sources
don't support is omitted.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from rental_agent.canonical.facts import FactRecorder
from rental_agent.config.logging import get_logger
from rental_agent.contracts import enums as e
from rental_agent.contracts.providers import LlmExecutor, LlmTaskRequest
from rental_agent.db.models import FactAssertion

log = get_logger(__name__)

TASK_TYPE = "nearby_poi_research"
PROMPT_VERSION = "poi-v1"
OUTPUT_SCHEMA_VERSION = "1"
FACT_KEY = "nearby_poi"
CACHE_DAYS = 30


class NearbyPoiOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    food_categories: list[str] = []  # cuisine categories only, never restaurant names
    stores: list[str] = []  # named supermarkets/retail within walking distance
    sources: list[str] = []  # URLs that support the findings
    summary: str = ""


_INSTRUCTIONS = (
    "Research what is ACTUALLY within walking distance (~10 minutes) of the given "
    "NYC-area location, using live web sources (Google Maps results pages, "
    "neighborhood guides, store locators). Report: (1) food_categories — cuisine "
    "CATEGORIES present nearby (e.g. Japanese, Korean, Chinese, Mexican, Italian, "
    "cafes) — NEVER individual restaurant names; (2) stores — NAMED supermarkets "
    "and major retail actually nearby (e.g. Costco, Target, Whole Foods, "
    "Trader Joe's, H Mart, key food markets); (3) sources — the URLs you used. "
    "Only include what your sources confirm for this specific area. If you cannot "
    "verify something, omit it. Never answer from memory alone."
)


class NearbyPoiResearchService:
    def __init__(self, session: Session, llm: LlmExecutor) -> None:
        self._s = session
        self._llm = llm
        self._facts = FactRecorder(session)

    def get_fresh(self, canonical_listing_id: uuid.UUID) -> dict[str, Any] | None:
        """Cached POI facts if researched within CACHE_DAYS."""
        latest = self._s.execute(
            select(FactAssertion)
            .where(
                FactAssertion.entity_id == canonical_listing_id,
                FactAssertion.fact_key == FACT_KEY,
            )
            .order_by(FactAssertion.asserted_at.desc())
        ).scalars().first()
        if latest is None or latest.value_json is None:
            return None
        asserted = latest.asserted_at
        if asserted.tzinfo is None:
            asserted = asserted.replace(tzinfo=UTC)
        if asserted < datetime.now(tz=UTC) - timedelta(days=CACHE_DAYS):
            return None
        value = latest.value_json.get("value")
        return value if isinstance(value, dict) else None

    def research(
        self, canonical_listing_id: uuid.UUID, area_description: str
    ) -> dict[str, Any] | None:
        """Run web research and record the fact; returns None on failure."""
        result = self._llm.execute(
            LlmTaskRequest(
                task_type=TASK_TYPE,
                prompt_version=PROMPT_VERSION,
                output_schema_version=OUTPUT_SCHEMA_VERSION,
                input_refs={"listing": str(canonical_listing_id)},
                input_payload={
                    "instructions": _INSTRUCTIONS,
                    "location": area_description,
                },
                output_schema=NearbyPoiOutput.model_json_schema(),
                tier=e.ModelTier.DEFAULT_HOSTED,
            )
        )
        if result.status is not e.ModelExecutionStatus.SUCCEEDED or result.output is None:
            log.warning(
                "poi_research_failed",
                listing=str(canonical_listing_id),
                error=result.error_code,
            )
            return None
        try:
            output = NearbyPoiOutput.model_validate(result.output)
        except ValidationError as exc:
            log.warning("poi_research_invalid", listing=str(canonical_listing_id), error=str(exc))
            return None
        if not output.sources:
            # Same posture as commute research: no sources, no fact (04 §19A).
            log.warning("poi_research_no_sources", listing=str(canonical_listing_id))
            return None
        value = output.model_dump()
        self._facts.record(
            entity_type=e.FactEntityType.LISTING,
            entity_id=canonical_listing_id,
            fact_key=FACT_KEY,
            value_json={"value": value},
            value_status=e.ValueStatus.ASSERTED,
            derivation_type=e.DerivationType.LLM_DERIVED,
            confidence=e.Confidence.MEDIUM,
            evidence_text=", ".join(output.sources[:5]),
        )
        return value
