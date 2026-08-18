"""ParsedSourceObservation envelope (03 §8) — the versioned adapter output contract.

Adapters normalize syntax only; they never decide cross-source canonical
identity. No contact fields exist anywhere in this contract (PR-ACQ-005).
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from rental_agent.contracts import enums as e

OBSERVATION_SCHEMA_VERSION = "1.0.0"


class _Block(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IdentityBlock(_Block):
    raw_address_text: str | None = None
    normalized_address_candidate: dict[str, Any] | None = None
    source_building_name: str | None = None
    raw_unit_label: str | None = None
    normalized_unit_candidate: str | None = None
    source_building_id: str | None = None
    source_geographic_labels: list[str] = Field(default_factory=list)
    evidence_locators: list[dict[str, Any]] = Field(default_factory=list)


class PricingBlock(_Block):
    source_price_text: str | None = None
    monthly_rent_minor: int | None = Field(default=None, ge=0)
    currency_code: str = "USD"
    price_type: str = "UNKNOWN"  # EXACT_MONTHLY_ASKING | STARTING_AT | RANGE |
    # NET_EFFECTIVE | GROSS_WITH_CONCESSION | CONTACT_FOR_PRICE | UNKNOWN (03 §14.1)
    range_min_minor: int | None = Field(default=None, ge=0)
    range_max_minor: int | None = Field(default=None, ge=0)
    concession_text: str | None = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class LayoutBlock(_Block):
    raw_layout_text: str | None = None
    source_bedrooms: float | None = None
    source_bathrooms: float | None = None
    proposed_layout_class: e.LayoutClass = e.LayoutClass.UNKNOWN
    qualifiers: list[str] = Field(default_factory=list)  # convertible/flex/alcove/railroad/...
    confidence: e.Confidence = e.Confidence.UNKNOWN
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class AvailabilityBlock(_Block):
    source_status_text: str | None = None
    available_from: str | None = None  # ISO date when stated
    proposed_status: e.AvailabilityStatus = e.AvailabilityStatus.UNKNOWN
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class DescriptionBlock(_Block):
    text: str | None = None  # contact-redacted
    sections: list[dict[str, Any]] = Field(default_factory=list)
    content_hash: str | None = None
    redaction_status: e.ContactRedactionStatus = e.ContactRedactionStatus.NOT_PRESENT
    language: str | None = None


class AmenityItem(_Block):
    label: str
    scope: e.AssertedScope = e.AssertedScope.UNKNOWN
    presence: e.PresenceStatus = e.PresenceStatus.PRESENT
    evidence: dict[str, Any] | None = None


class LaundryBlock(_Block):
    proposed_laundry_type: e.LaundryType = e.LaundryType.UNKNOWN
    scope: e.AssertedScope = e.AssertedScope.UNKNOWN
    evidence_text: str | None = None
    evidence_locator: dict[str, Any] | None = None
    confidence: e.Confidence = e.Confidence.UNKNOWN


class MediaReference(_Block):
    url: str
    source_media_id: str | None = None
    source_order: int | None = None
    caption: str | None = None
    alt_text: str | None = None
    proposed_type: e.MediaType = e.MediaType.UNKNOWN
    source_association: str | None = None  # listing | unit | building | layout | unknown
    appears_floor_plan: bool = False


class ExtractionBlock(_Block):
    adapter_version: str
    extraction_paths: list[str] = Field(default_factory=list)
    model_execution_refs: list[str] = Field(default_factory=list)
    confidence: e.Confidence = e.Confidence.UNKNOWN
    fields_requiring_review: list[str] = Field(default_factory=list)
    missing_structural_markers: list[str] = Field(default_factory=list)


class ValidationBlock(_Block):
    parse_status: e.ParseStatus = e.ParseStatus.VALID
    issues: list[dict[str, Any]] = Field(default_factory=list)


class ParsedSourceObservation(_Block):
    schema_version: str = OBSERVATION_SCHEMA_VERSION
    source_code: str
    source_native_id: str | None = None
    source_url: str
    observed_at: datetime
    retrieved_at: datetime
    source_status: str = "UNKNOWN"  # AVAILABLE | FUTURE | PENDING | UNAVAILABLE | UNKNOWN
    identity: IdentityBlock = Field(default_factory=IdentityBlock)
    pricing: PricingBlock = Field(default_factory=PricingBlock)
    layout: LayoutBlock = Field(default_factory=LayoutBlock)
    availability: AvailabilityBlock = Field(default_factory=AvailabilityBlock)
    description: DescriptionBlock = Field(default_factory=DescriptionBlock)
    amenities: list[AmenityItem] = Field(default_factory=list)
    laundry: LaundryBlock = Field(default_factory=LaundryBlock)
    media_references: list[MediaReference] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    extraction: ExtractionBlock
    validation: ValidationBlock = Field(default_factory=ValidationBlock)
