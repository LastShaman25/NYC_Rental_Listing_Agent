"""Detail-page enrichment: facts with provenance, idempotency, override respect."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.conftest import requires_db

from rental_agent.contracts import enums as e
from rental_agent.contracts.providers import LlmTaskRequest, LlmTaskResult
from rental_agent.db.models import (
    Address,
    Building,
    CanonicalListing,
    FactAssertion,
    HumanOverride,
    ListingSourceLink,
    MediaAsset,
    RefreshRun,
    SourceObservation,
    SourceRun,
)
from rental_agent.enrichment.listing_content.service import (
    ListingContentEnrichmentService,
    TavilyExtractClient,
)

pytestmark = requires_db

NOW = datetime.now(tz=UTC)


class FakeExtract(TavilyExtractClient):
    def __init__(self, content: str | None) -> None:
        self._content = content

    def extract(self, url: str) -> str | None:
        return self._content


class FakeLlm:
    interface_version = "1.0.0"
    provider_code = "fake"

    def __init__(self, output: dict) -> None:
        self._output = output
        self.calls = 0

    def execute(self, request: LlmTaskRequest) -> LlmTaskResult:
        self.calls += 1
        return LlmTaskResult(
            status=e.ModelExecutionStatus.SUCCEEDED,
            output=self._output,
            model_id="fake-model",
        )


def _listing_with_link(db_session: Session, source_id: uuid.UUID) -> uuid.UUID:
    address = Address(
        locality="NY", administrative_area="NY", formatted_address=f"e-{uuid.uuid4().hex[:6]}"
    )
    db_session.add(address)
    db_session.flush()
    building = Building(address_id=address.address_id)
    db_session.add(building)
    db_session.flush()
    listing = CanonicalListing(
        building_id=building.building_id,
        layout_class="ONE_BEDROOM",
        lifecycle_status="ACTIVE",
        first_seen_at=NOW,
        last_seen_at=NOW,
        last_material_change_at=NOW,
    )
    db_session.add(listing)
    db_session.flush()
    run = RefreshRun(
        trigger_type="MANUAL",
        logical_run_key=f"e:{uuid.uuid4().hex}",
        started_at=NOW,
        pipeline_version="t",
    )
    db_session.add(run)
    db_session.flush()
    source_run = SourceRun(
        refresh_run_id=run.refresh_run_id,
        source_id=source_id,
        started_at=NOW,
        adapter_version="t",
        status="HEALTHY",
        health_gate_passed=True,
    )
    db_session.add(source_run)
    db_session.flush()
    observation = SourceObservation(
        source_id=source_id,
        source_run_id=source_run.source_run_id,
        source_native_id=uuid.uuid4().hex[:8],
        source_url=f"https://e.test/{uuid.uuid4().hex[:8]}",
        observed_at=NOW,
        retrieved_at=NOW,
        content_hash=uuid.uuid4().hex,
        parsed_payload={},
        parse_status="VALID",
        contact_redaction_status="NOT_PRESENT",
        adapter_version="t",
        schema_version="1",
    )
    db_session.add(observation)
    db_session.flush()
    db_session.add(
        ListingSourceLink(
            canonical_listing_id=listing.canonical_listing_id,
            source_id=source_id,
            source_native_id=observation.source_native_id,
            source_url=observation.source_url,
            first_observation_id=observation.source_observation_id,
            latest_observation_id=observation.source_observation_id,
            first_seen_at=NOW,
            last_seen_at=NOW,
            link_status="ACTIVE",
            identity_method="SOURCE_NATIVE_CONTINUITY",
            identity_confidence="HIGH",
            identity_rule_version="t",
        )
    )
    db_session.commit()
    return listing.canonical_listing_id


_RICH_OUTPUT = {
    "laundry_type": "IN_UNIT_WASHER_DRYER_CONFIRMED",
    "laundry_evidence": "washer/dryer in unit",
    "floor_plan_present": True,
    "floor_plan_url": "https://e.test/plan.png",
    "amenities": ["Gym", "Doorman"],
    "fee_status": "NO_FEE",
    "fee_evidence": "no broker fee",
    "monthly_rent_usd": 3902,
    "rent_evidence": "$3,902/month",
}


def test_enrich_writes_facts_media_and_materializes(db_session, seeded_source) -> None:
    listing_id = _listing_with_link(db_session, seeded_source)
    service = ListingContentEnrichmentService(
        db_session, FakeLlm(_RICH_OUTPUT), FakeExtract("page text with facts")
    )
    outcome = service.enrich(listing_id)
    db_session.commit()
    assert outcome.status == "ENRICHED"
    listing = db_session.get(CanonicalListing, listing_id)
    assert listing.laundry_type == "IN_UNIT_WASHER_DRYER_CONFIRMED"
    assert listing.indoor_laundry_badge_eligible is False  # badge never granted here
    keys = {
        a.fact_key
        for a in db_session.execute(
            select(FactAssertion).where(FactAssertion.entity_id == listing_id)
        ).scalars()
    }
    assert {"laundry_type", "fee_status", "amenities", "detail_extract_hash"} <= keys
    plan = db_session.execute(
        select(MediaAsset).where(MediaAsset.source_url == "https://e.test/plan.png")
    ).scalar_one()
    assert plan.media_type == "FLOOR_PLAN"
    # Page-stated gross rent corrects the snippet-parsed value, with an event.
    assert listing.monthly_rent_minor == 390_200
    from rental_agent.db.models import ListingEvent

    price_event = db_session.execute(
        select(ListingEvent).where(
            ListingEvent.canonical_listing_id == listing_id,
            ListingEvent.event_type == "PRICE_CHANGED",
        )
    ).scalar_one()
    assert price_event.after_values["monthly_rent_minor"] == 390_200


def test_unchanged_page_is_skipped(db_session, seeded_source) -> None:
    listing_id = _listing_with_link(db_session, seeded_source)
    llm = FakeLlm(_RICH_OUTPUT)
    service = ListingContentEnrichmentService(db_session, llm, FakeExtract("same page"))
    assert service.enrich(listing_id).status == "ENRICHED"
    db_session.commit()
    assert service.enrich(listing_id).status == "SKIPPED_UNCHANGED"
    assert llm.calls == 1  # second pass never reached the LLM


def test_active_override_blocks_materialization(db_session, seeded_source) -> None:
    listing_id = _listing_with_link(db_session, seeded_source)
    db_session.add(
        HumanOverride(
            entity_type="LISTING",
            entity_id=listing_id,
            field_name="laundry_type",
            override_value={"value": "EXPLICITLY_NO_LAUNDRY"},
            reason_code="CLASSIFICATION_CORRECTION",
            reason_text="operator checked in person",
            created_by="test_operator",
            override_status="ACTIVE",
            review_on_new_conflict=True,
        )
    )
    db_session.commit()
    service = ListingContentEnrichmentService(
        db_session, FakeLlm(_RICH_OUTPUT), FakeExtract("conflicting page")
    )
    outcome = service.enrich(listing_id)
    db_session.commit()
    assert outcome.status == "ENRICHED"
    listing = db_session.get(CanonicalListing, listing_id)
    # Override wins: the LLM assertion is evidence only, never materialized.
    assert listing.laundry_type == "UNKNOWN"


def test_extract_failure_is_reported(db_session, seeded_source) -> None:
    listing_id = _listing_with_link(db_session, seeded_source)
    service = ListingContentEnrichmentService(
        db_session, FakeLlm(_RICH_OUTPUT), FakeExtract(None)
    )
    assert service.enrich(listing_id).status == "EXTRACT_FAILED"
