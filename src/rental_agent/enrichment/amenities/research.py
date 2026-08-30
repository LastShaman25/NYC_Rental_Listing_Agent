"""Amenity research for properties whose pages we could not (or cannot
currently) extract — owner request 2026-08-30: amenity information for ALL
properties, company and regular.

Same posture as commute/POI research (04 §19A): the hosted web-research
executor looks at the building's official site / listing pages on the live
web, reports ONLY explicitly stated amenities, must cite sources, and model
memory is forbidden — no sources, no fact. Page-extracted facts remain the
preferred source; a later successful page check simply supersedes these.
"""

import uuid

from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy.orm import Session

from rental_agent.canonical.facts import FactRecorder
from rental_agent.config.logging import get_logger
from rental_agent.contracts import enums as e
from rental_agent.contracts.providers import LlmExecutor, LlmTaskRequest
from rental_agent.db.models import CompanyProperty

log = get_logger(__name__)

TASK_TYPE = "amenity_research"
PROMPT_VERSION = "amenity-v1"
OUTPUT_SCHEMA_VERSION = "1"
FACT_KEY = "amenities"


class AmenityResearchOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amenities: list[str] = []
    laundry_type: str = "UNKNOWN"  # a LaundryType value
    fee_status: str = "UNKNOWN"  # NO_FEE | FEE_CHARGED | UNKNOWN
    sources: list[str] = []  # URLs that support the findings — REQUIRED
    summary: str = ""


_INSTRUCTIONS = (
    "Research the building/unit amenities of the given NYC-area rental "
    "property using live web sources (the building's official leasing site "
    "and listing pages). Report ONLY amenities those pages explicitly state "
    "(gym, doorman, elevator, roof deck, pool, dishwasher, parking, bike "
    "room, storage, package room, live-in super...), as short English "
    "labels. laundry_type must be one of "
    + ", ".join(t.value for t in e.LaundryType)
    + " — UNKNOWN unless laundry is explicitly described. fee_status NO_FEE "
    "only if a page explicitly says no broker fee; FEE_CHARGED only if a fee "
    "is explicitly stated; otherwise UNKNOWN. sources: the URLs you used — "
    "required. Verify you are looking at THIS property (name/address match). "
    "If you cannot verify something, omit it. Never answer from memory alone."
)


class AmenityResearchService:
    def __init__(self, session: Session, llm: LlmExecutor) -> None:
        self._s = session
        self._llm = llm
        self._facts = FactRecorder(session)

    def research(
        self, *, name: str, address: str, hint_url: str | None = None
    ) -> AmenityResearchOutput | None:
        """Run web research; returns validated output or None (no sources /
        failure). Persisting is the caller's choice via the apply helpers."""
        result = self._llm.execute(
            LlmTaskRequest(
                task_type=TASK_TYPE,
                prompt_version=PROMPT_VERSION,
                output_schema_version=OUTPUT_SCHEMA_VERSION,
                input_refs={"property": name},
                input_payload={
                    "instructions": _INSTRUCTIONS,
                    "property_name": name,
                    "address": address,
                    "known_page": hint_url,
                },
                output_schema=AmenityResearchOutput.model_json_schema(),
                tier=e.ModelTier.DEFAULT_HOSTED,
            )
        )
        if result.status is not e.ModelExecutionStatus.SUCCEEDED or result.output is None:
            log.warning("amenity_research_failed", name=name, error=result.error_code)
            return None
        try:
            output = AmenityResearchOutput.model_validate(result.output)
        except ValidationError as exc:
            log.warning("amenity_research_invalid", name=name, error=str(exc))
            return None
        if not output.sources:
            # Same posture as commute research: no sources, no fact (04 §19A).
            log.warning("amenity_research_no_sources", name=name)
            return None
        if not output.amenities and output.laundry_type == "UNKNOWN":
            log.info("amenity_research_empty", name=name)
            return None
        return output

    def record_listing_fact(
        self, canonical_listing_id: uuid.UUID, output: AmenityResearchOutput
    ) -> None:
        """Record researched amenities through the normal fact pipeline
        (LLM_DERIVED, sources as evidence) — the detail page and Studio pick
        them up exactly like page-extracted amenities."""
        amenities = [a.strip() for a in output.amenities if a.strip()][:25]
        if not amenities:
            return
        self._facts.record(
            entity_type=e.FactEntityType.LISTING,
            entity_id=canonical_listing_id,
            fact_key=FACT_KEY,
            value_json={"value": amenities},
            value_status=e.ValueStatus.ASSERTED,
            derivation_type=e.DerivationType.LLM_DERIVED,
            confidence=e.Confidence.MEDIUM,
            evidence_text=("web-researched: " + ", ".join(output.sources[:5]))[:500],
        )

    @staticmethod
    def apply_to_company(prop: CompanyProperty, output: AmenityResearchOutput) -> None:
        """Merge researched facts into the availability snapshot. Page-stated
        values are never overwritten — research only fills UNKNOWN gaps."""
        availability = dict(prop.availability or {})
        if not availability.get("amenities"):
            availability["amenities"] = [
                a.strip() for a in output.amenities if a.strip()
            ][:25]
            availability["amenities_sources"] = output.sources[:5]
        if (
            availability.get("laundry_type") in (None, "", "UNKNOWN")
            and output.laundry_type in {t.value for t in e.LaundryType}
            and output.laundry_type != "UNKNOWN"
        ):
            availability["laundry_type"] = output.laundry_type
            availability["laundry_evidence"] = (
                "web-researched: " + ", ".join(output.sources[:3])
            )[:300]
        if (
            availability.get("fee_status") in (None, "", "UNKNOWN")
            and output.fee_status in ("NO_FEE", "FEE_CHARGED")
        ):
            availability["fee_status"] = output.fee_status
            availability["fee_evidence"] = (
                "web-researched: " + ", ".join(output.sources[:3])
            )[:300]
        prop.availability = availability
