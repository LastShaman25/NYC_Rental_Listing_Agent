"""Observation → canonical normalization (Phase 3 skeleton; 02 §9, 06 §15).

Turns one persisted source observation into canonical state:

- NEW source identity → provisional Address → Building → CanonicalListing chain
  plus a ListingSourceLink and a CREATED listing event.
- Known identity, identical content hash → freshness update only (no history).
- Known identity, changed content → materialized field updates plus typed
  listing events (price/availability/material), never last-write-wins deletes.

Cross-source identity (02 §9.1 hierarchy):
- Step 1: within-source native-ID/URL continuity.
- Step 2: exact normalized building + exact normalized unit → attach the new
  source link to the existing canonical listing (EXACT_ADDRESS_AND_UNIT).
- Same building + same layout + rent within tolerance but no unit evidence →
  reviewable PENDING duplicate_candidate; never an automatic merge (02 §9.3).
Strong multi-field/probabilistic matching remains future Phase 3 work.

Everything is idempotent under replay: listing events carry an idempotency key
derived from the causing observation, and re-running the same observation makes
no additional canonical changes.

Nothing here touches marketing selection, shortlists, or lifecycle inactivation
(03 §21.2), and SEARCH_INDEX-discovered links never support disappearance.
"""

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from rental_agent.canonical.facts import FactRecorder
from rental_agent.contracts import enums as e
from rental_agent.contracts.observation import ParsedSourceObservation
from rental_agent.db.models import (
    Address,
    Building,
    CanonicalListing,
    DuplicateCandidate,
    ListingEvent,
    ListingSourceLink,
    ReviewIssue,
    SourceObservation,
    Unit,
)
from rental_agent.validation.laundry import derive_badge_eligibility

IDENTITY_RULE_VERSION = "phase3-skeleton-2"
# Rent proximity band for duplicate-candidate generation (calibration input,
# not a merge threshold; candidates always go to review).
RENT_SIMILARITY_TOLERANCE = 0.02


def unit_fingerprint(raw: str) -> str:
    """'4A', '4-A', 'APT 4A', '#4a' normalize to one within-building key (04 §7.3)."""
    text = raw.upper().strip()
    text = re.sub(r"^(APT|UNIT|STE|SUITE|NO)\.?\s*", "", text)
    return re.sub(r"[\s\-#.]", "", text)


def address_fingerprint(raw: str) -> str:
    """Deterministic normalized match key: lowercase, collapse whitespace,
    normalize common suffixes/punctuation (04 §7.3 — syntax only)."""
    text = raw.lower().strip()
    text = re.sub(r"[.,#]", " ", text)
    replacements = {
        r"\bstreet\b": "st",
        r"\bavenue\b": "ave",
        r"\bboulevard\b": "blvd",
        r"\broad\b": "rd",
        r"\bplace\b": "pl",
        r"\bdrive\b": "dr",
        r"\blane\b": "ln",
        r"\bterrace\b": "ter",
        r"\bparkway\b": "pkwy",
        r"\beast\b": "e",
        r"\bwest\b": "w",
        r"\bnorth\b": "n",
        r"\bsouth\b": "s",
    }
    for pattern, repl in replacements.items():
        text = re.sub(pattern, repl, text)
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class NormalizationOutcome:
    classification: str  # NEW | UNCHANGED | MATERIAL_CHANGE | UNRESOLVED
    canonical_listing_id: uuid.UUID | None = None
    listing_source_link_id: uuid.UUID | None = None
    events_emitted: list[str] = field(default_factory=list)


class NormalizationService:
    def __init__(self, session: Session) -> None:
        self._s = session

    def process_observation(
        self,
        source_observation_id: uuid.UUID,
        *,
        discovery_method: e.DiscoveryMethod,
    ) -> NormalizationOutcome:
        row = self._s.get(SourceObservation, source_observation_id)
        if row is None:
            raise LookupError(f"observation {source_observation_id} not found")
        if row.parse_status not in (e.ParseStatus.VALID.value, e.ParseStatus.PARTIAL.value):
            return NormalizationOutcome(classification="UNRESOLVED")
        observation = ParsedSourceObservation.model_validate(row.parsed_payload)

        link = self._find_link(row)
        if link is None:
            return self._create_canonical(row, observation, discovery_method)
        return self._update_existing(row, observation, link)

    # -- within-source identity (hierarchy step 1) ----------------------------

    def _find_link(self, row: SourceObservation) -> ListingSourceLink | None:
        if row.source_native_id is not None:
            return self._s.execute(
                select(ListingSourceLink).where(
                    ListingSourceLink.source_id == row.source_id,
                    ListingSourceLink.source_native_id == row.source_native_id,
                )
            ).scalar_one_or_none()
        return self._s.execute(
            select(ListingSourceLink).where(
                ListingSourceLink.source_id == row.source_id,
                ListingSourceLink.source_url == row.source_url,
            )
        ).scalar_one_or_none()

    # -- new canonical chain ---------------------------------------------------

    def _create_canonical(
        self,
        row: SourceObservation,
        observation: ParsedSourceObservation,
        discovery_method: e.DiscoveryMethod,
    ) -> NormalizationOutcome:
        raw_address = observation.identity.raw_address_text
        locality = (
            observation.identity.source_geographic_labels[0]
            if observation.identity.source_geographic_labels
            else "UNRESOLVED"  # never invent a municipality (04 §7.3)
        )
        address = None
        if raw_address:
            fingerprint = address_fingerprint(raw_address)
            address = self._s.execute(
                select(Address).where(Address.address_fingerprint == fingerprint)
            ).scalar_one_or_none()
            if address is None:
                address = Address(
                    address_line_1=raw_address,
                    locality=locality,
                    administrative_area="NY" if "NJ" not in locality.upper() else "NJ",
                    formatted_address=raw_address,
                    address_fingerprint=fingerprint,
                )
                self._s.add(address)
                self._s.flush()
        else:
            # Address withheld: provisional placeholder address per source URL so
            # the building chain exists; boundary stays UNRESOLVED for review.
            address = Address(
                locality=locality,
                administrative_area="NY",
                formatted_address=f"[address unresolved] {row.source_url}",
                address_fingerprint=f"unresolved:{row.source_url}",
            )
            self._s.add(address)
            self._s.flush()

        building = self._s.execute(
            select(Building).where(Building.address_id == address.address_id)
        ).scalar_one_or_none()
        if building is None:
            building = Building(address_id=address.address_id)
            self._s.add(building)
            self._s.flush()

        # Cross-source identity, hierarchy step 2 (02 §9.1): exact normalized
        # building + exact normalized unit attaches this source to the existing
        # canonical listing instead of creating a duplicate.
        unit = None
        unit_label = (
            observation.identity.raw_unit_label or observation.identity.normalized_unit_candidate
        )
        if unit_label:
            fingerprint = unit_fingerprint(unit_label)
            unit = self._s.execute(
                select(Unit).where(
                    Unit.building_id == building.building_id,
                    Unit.unit_fingerprint == fingerprint,
                )
            ).scalar_one_or_none()
            if unit is not None:
                existing = self._s.execute(
                    select(CanonicalListing)
                    .where(
                        CanonicalListing.unit_id == unit.unit_id,
                        CanonicalListing.lifecycle_status != e.LifecycleStatus.MERGED.value,
                    )
                    .order_by(CanonicalListing.last_seen_at.desc())
                    .limit(1)
                ).scalar_one_or_none()
                if existing is not None:
                    return self._attach_cross_source_link(row, existing, discovery_method)
            else:
                unit = Unit(
                    building_id=building.building_id,
                    canonical_unit_label=unit_label,
                    unit_fingerprint=fingerprint,
                    layout_class=observation.layout.proposed_layout_class.value,
                )
                self._s.add(unit)
                self._s.flush()

        # Hierarchy step 3 (02 §9.2 STRONG_MULTI_FIELD): no unit evidence, but a
        # strict conjunction of strong signals — same building AND same layout
        # AND identical rent AND fresh overlap AND exactly ONE such match.
        # Ambiguity (multiple matches) falls through to duplicate candidates.
        if unit is None:
            strong = self._strong_multi_field_match(building, observation, row)
            if strong is not None:
                return self._attach_cross_source_link(
                    row,
                    strong,
                    discovery_method,
                    identity_method=e.IdentityMethod.STRONG_MULTI_FIELD,
                    identity_confidence=e.IdentityConfidence.MEDIUM,
                )

        listing = CanonicalListing(
            building_id=building.building_id,
            unit_id=unit.unit_id if unit is not None else None,
            layout_class=observation.layout.proposed_layout_class.value,
            bedroom_count=observation.layout.source_bedrooms,
            bathroom_count=observation.layout.source_bathrooms,
            monthly_rent_minor=observation.pricing.monthly_rent_minor,
            availability_status=observation.availability.proposed_status.value,
            laundry_type=observation.laundry.proposed_laundry_type.value,
            description_current=observation.description.text,
            first_seen_at=row.observed_at,
            last_seen_at=row.observed_at,
            last_material_change_at=row.observed_at,
            lifecycle_status=e.LifecycleStatus.CANDIDATE.value,
            canonical_resolution_status=e.CanonicalResolutionStatus.PROVISIONAL.value,
        )
        self._s.add(listing)
        self._s.flush()

        link = ListingSourceLink(
            canonical_listing_id=listing.canonical_listing_id,
            source_id=row.source_id,
            source_native_id=row.source_native_id,
            source_url=row.source_url,
            first_observation_id=row.source_observation_id,
            latest_observation_id=row.source_observation_id,
            first_seen_at=row.observed_at,
            last_seen_at=row.observed_at,
            link_status=e.LinkStatus.ACTIVE.value,
            discovery_method=discovery_method.value,
            identity_method=e.IdentityMethod.SOURCE_NATIVE_CONTINUITY.value,
            identity_confidence=e.IdentityConfidence.HIGH.value,
            identity_rule_version=IDENTITY_RULE_VERSION,
        )
        self._s.add(link)
        self._s.flush()

        emitted = self._emit_event(
            listing.canonical_listing_id,
            e.ListingEventType.CREATED,
            row,
            after_values={"lifecycle_status": listing.lifecycle_status},
        )
        self._record_listing_facts(listing.canonical_listing_id, observation, row)
        self._generate_duplicate_candidates(listing, building)
        return NormalizationOutcome(
            classification="NEW",
            canonical_listing_id=listing.canonical_listing_id,
            listing_source_link_id=link.listing_source_link_id,
            events_emitted=emitted,
        )

    def _record_listing_facts(
        self,
        canonical_listing_id: uuid.UUID,
        observation: ParsedSourceObservation,
        row: SourceObservation,
    ) -> None:
        """Evidence-backed assertions + current resolutions for high-value facts."""
        recorder = FactRecorder(self._s)

        def record(fact_key: str, value, confidence: e.Confidence, evidence: str | None) -> None:
            recorder.record(
                entity_type=e.FactEntityType.LISTING,
                entity_id=canonical_listing_id,
                fact_key=fact_key,
                value_json={"value": value},
                value_status=e.ValueStatus.ASSERTED,
                derivation_type=e.DerivationType.SOURCE_TEXT,
                confidence=confidence,
                source_observation_id=row.source_observation_id,
                evidence_text=evidence,
            )

        if observation.pricing.monthly_rent_minor is not None:
            record(
                "monthly_rent_minor",
                observation.pricing.monthly_rent_minor,
                e.Confidence.MEDIUM,
                observation.pricing.source_price_text,
            )
        if observation.layout.proposed_layout_class is not e.LayoutClass.UNKNOWN:
            record(
                "layout_class",
                observation.layout.proposed_layout_class.value,
                observation.layout.confidence,
                observation.layout.raw_layout_text,
            )
        if observation.laundry.proposed_laundry_type is not e.LaundryType.UNKNOWN:
            record(
                "laundry_type",
                observation.laundry.proposed_laundry_type.value,
                observation.laundry.confidence,
                observation.laundry.evidence_text,
            )
        if observation.availability.proposed_status is not e.AvailabilityStatus.UNKNOWN:
            record(
                "availability_status",
                observation.availability.proposed_status.value,
                e.Confidence.MEDIUM,
                observation.availability.source_status_text,
            )

    def _strong_multi_field_match(
        self,
        building: Building,
        observation: ParsedSourceObservation,
        row: SourceObservation,
    ) -> CanonicalListing | None:
        """Exactly one same-building listing matching layout + identical rent.

        Cross-source only: a listing already linked to THIS source is never a
        match — one source exposing two identical native IDs in a building
        almost certainly means two distinct physical units. Any ambiguity
        (multiple matches) returns None (02 §9.3)."""
        layout = observation.layout.proposed_layout_class
        rent = observation.pricing.monthly_rent_minor
        if layout in (e.LayoutClass.UNKNOWN, e.LayoutClass.CONFLICTING) or rent is None:
            return None
        same_source_link = (
            select(ListingSourceLink.listing_source_link_id)
            .where(
                ListingSourceLink.canonical_listing_id == CanonicalListing.canonical_listing_id,
                ListingSourceLink.source_id == row.source_id,
            )
            .exists()
        )
        matches = (
            self._s.execute(
                select(CanonicalListing).where(
                    CanonicalListing.building_id == building.building_id,
                    CanonicalListing.layout_class == layout.value,
                    CanonicalListing.monthly_rent_minor == rent,  # identical, not similar
                    CanonicalListing.unit_id.is_(None),  # unit-labeled listings need unit proof
                    CanonicalListing.lifecycle_status.notin_(
                        [e.LifecycleStatus.MERGED.value, e.LifecycleStatus.INACTIVE.value]
                    ),
                    ~same_source_link,
                )
            )
            .scalars()
            .all()
        )
        return matches[0] if len(matches) == 1 else None

    def _attach_cross_source_link(
        self,
        row: SourceObservation,
        listing: CanonicalListing,
        discovery_method: e.DiscoveryMethod,
        *,
        identity_method: e.IdentityMethod = e.IdentityMethod.EXACT_ADDRESS_AND_UNIT,
        identity_confidence: e.IdentityConfidence = e.IdentityConfidence.HIGH,
    ) -> NormalizationOutcome:
        """New source for an existing canonical listing: one listing, separate
        provenance (PR-ACQ-003)."""
        link = ListingSourceLink(
            canonical_listing_id=listing.canonical_listing_id,
            source_id=row.source_id,
            source_native_id=row.source_native_id,
            source_url=row.source_url,
            first_observation_id=row.source_observation_id,
            latest_observation_id=row.source_observation_id,
            first_seen_at=row.observed_at,
            last_seen_at=row.observed_at,
            link_status=e.LinkStatus.ACTIVE.value,
            discovery_method=discovery_method.value,
            identity_method=identity_method.value,
            identity_confidence=identity_confidence.value,
            identity_rule_version=IDENTITY_RULE_VERSION,
        )
        self._s.add(link)
        listing.last_seen_at = max(listing.last_seen_at, row.observed_at)
        self._s.flush()
        return NormalizationOutcome(
            classification="MATCHED_EXISTING",
            canonical_listing_id=listing.canonical_listing_id,
            listing_source_link_id=link.listing_source_link_id,
        )

    def _generate_duplicate_candidates(self, listing: CanonicalListing, building: Building) -> None:
        """Same building + same layout + similar rent is a reviewable candidate,
        never an automatic merge (02 §9.3: no single weak signal merges)."""
        if listing.monthly_rent_minor is None or listing.layout_class in (
            e.LayoutClass.UNKNOWN.value,
            e.LayoutClass.CONFLICTING.value,
        ):
            return
        others = (
            self._s.execute(
                select(CanonicalListing).where(
                    CanonicalListing.building_id == building.building_id,
                    CanonicalListing.canonical_listing_id != listing.canonical_listing_id,
                    CanonicalListing.layout_class == listing.layout_class,
                    CanonicalListing.monthly_rent_minor.is_not(None),
                    CanonicalListing.lifecycle_status != e.LifecycleStatus.MERGED.value,
                )
            )
            .scalars()
            .all()
        )
        for other in others:
            if other.monthly_rent_minor is None:  # filtered in SQL; narrows type
                continue
            rent_delta = abs(other.monthly_rent_minor - listing.monthly_rent_minor)
            if rent_delta > RENT_SIMILARITY_TOLERANCE * listing.monthly_rent_minor:
                continue
            a_id, b_id = sorted(
                (listing.canonical_listing_id, other.canonical_listing_id),
                key=str,
            )
            stmt = (
                pg_insert(DuplicateCandidate)
                .values(
                    listing_a_id=a_id,
                    listing_b_id=b_id,
                    evidence={
                        "rule": "same_building_layout_similar_rent",
                        "layout_class": listing.layout_class,
                        "rent_delta_minor": rent_delta,
                        "tolerance": RENT_SIMILARITY_TOLERANCE,
                    },
                    rule_version=IDENTITY_RULE_VERSION,
                    status=e.DuplicateCandidateStatus.PENDING.value,
                )
                .on_conflict_do_nothing()
                .returning(DuplicateCandidate.duplicate_candidate_id)
            )
            candidate_id = self._s.execute(stmt).scalar_one_or_none()
            if candidate_id is not None:
                # Surface for human resolution in the review queue (07 §17).
                self._s.add(
                    ReviewIssue(
                        entity_type=e.FactEntityType.LISTING.value,
                        entity_id=a_id,
                        issue_type=e.ReviewIssueType.DUPLICATE_CANDIDATE.value,
                        severity=e.ReviewIssueSeverity.WARNING.value,
                        details={
                            "duplicate_candidate_id": str(candidate_id),
                            "listing_a_id": str(a_id),
                            "listing_b_id": str(b_id),
                        },
                    )
                )

    # -- existing identity ----------------------------------------------------

    def _update_existing(
        self,
        row: SourceObservation,
        observation: ParsedSourceObservation,
        link: ListingSourceLink,
    ) -> NormalizationOutcome:
        previous = self._s.get(SourceObservation, link.latest_observation_id)
        listing = self._s.get(CanonicalListing, link.canonical_listing_id)
        assert listing is not None

        # Replaying the exact same observation row: nothing to do (02 §27.1).
        if link.latest_observation_id == row.source_observation_id:
            return NormalizationOutcome(
                classification="UNCHANGED",
                canonical_listing_id=listing.canonical_listing_id,
                listing_source_link_id=link.listing_source_link_id,
            )

        self._touch_freshness(link, listing, row)
        if previous is not None and previous.content_hash == row.content_hash:
            return NormalizationOutcome(
                classification="UNCHANGED",
                canonical_listing_id=listing.canonical_listing_id,
                listing_source_link_id=link.listing_source_link_id,
            )

        # Evidence is always recorded, even when an override blocks application.
        self._record_listing_facts(listing.canonical_listing_id, observation, row)
        recorder = FactRecorder(self._s)

        def override_blocks(fact_key: str, incoming) -> bool:
            override = recorder.active_override(
                e.FactEntityType.LISTING, listing.canonical_listing_id, fact_key
            )
            if override is None:
                return False
            override_value = (override.override_value or {}).get("value")
            if incoming != override_value:
                recorder.raise_conflict_with_override(
                    override,
                    entity_id=listing.canonical_listing_id,
                    fact_key=fact_key,
                    incoming_value=incoming,
                )
            return True  # active override always outranks source evidence

        emitted: list[str] = []
        new_rent = observation.pricing.monthly_rent_minor
        if (
            new_rent is not None
            and new_rent != listing.monthly_rent_minor
            and not override_blocks("monthly_rent_minor", new_rent)
        ):
            emitted += self._emit_event(
                listing.canonical_listing_id,
                e.ListingEventType.PRICE_CHANGED,
                row,
                before_values={"monthly_rent_minor": listing.monthly_rent_minor},
                after_values={"monthly_rent_minor": new_rent},
            )
            listing.monthly_rent_minor = new_rent

        new_availability = observation.availability.proposed_status.value
        if (
            new_availability != e.AvailabilityStatus.UNKNOWN.value
            and new_availability != listing.availability_status
            and not override_blocks("availability_status", new_availability)
        ):
            emitted += self._emit_event(
                listing.canonical_listing_id,
                e.ListingEventType.AVAILABILITY_CHANGED,
                row,
                before_values={"availability_status": listing.availability_status},
                after_values={"availability_status": new_availability},
            )
            listing.availability_status = new_availability

        new_laundry = observation.laundry.proposed_laundry_type
        if (
            new_laundry is not e.LaundryType.UNKNOWN
            and new_laundry.value != listing.laundry_type
            and not override_blocks("laundry_type", new_laundry.value)
        ):
            emitted += self._emit_event(
                listing.canonical_listing_id,
                e.ListingEventType.LAUNDRY_CHANGED,
                row,
                before_values={"laundry_type": listing.laundry_type},
                after_values={"laundry_type": new_laundry.value},
            )
            listing.laundry_type = new_laundry.value
            # Snippet-derived laundry is unvalidated: the badge stays derived
            # and conservative (02 §12.3) — PENDING validation can never be true.
            listing.indoor_laundry_badge_eligible = derive_badge_eligibility(
                new_laundry,
                e.ValidationStatus.PENDING,
                e.ResolutionStatus.RESOLVED,
            )

        if emitted:
            listing.last_material_change_at = row.observed_at
            return NormalizationOutcome(
                classification="MATERIAL_CHANGE",
                canonical_listing_id=listing.canonical_listing_id,
                listing_source_link_id=link.listing_source_link_id,
                events_emitted=emitted,
            )
        return NormalizationOutcome(
            classification="UNCHANGED",
            canonical_listing_id=listing.canonical_listing_id,
            listing_source_link_id=link.listing_source_link_id,
        )

    def _touch_freshness(
        self, link: ListingSourceLink, listing: CanonicalListing, row: SourceObservation
    ) -> None:
        if row.observed_at >= link.last_seen_at:
            link.last_seen_at = row.observed_at
            link.latest_observation_id = row.source_observation_id
        listing.last_seen_at = max(listing.last_seen_at, row.observed_at)

    def _emit_event(
        self,
        canonical_listing_id: uuid.UUID,
        event_type: e.ListingEventType,
        row: SourceObservation,
        *,
        before_values: dict | None = None,
        after_values: dict | None = None,
        event_time: datetime | None = None,
    ) -> list[str]:
        """Idempotent event append: the key ties the event to its causing
        observation, so replay emits nothing new (02 §17.1)."""
        key = f"{canonical_listing_id}:{event_type.value}:{row.source_observation_id}"
        stmt = (
            pg_insert(ListingEvent)
            .values(
                canonical_listing_id=canonical_listing_id,
                event_type=event_type.value,
                event_time=event_time or row.observed_at,
                source_observation_id=row.source_observation_id,
                before_values=before_values,
                after_values=after_values,
                idempotency_key=key,
            )
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
            .returning(ListingEvent.listing_event_id)
        )
        inserted = self._s.execute(stmt).scalar_one_or_none()
        return [event_type.value] if inserted is not None else []
