"""Commute research service invariants (04 §19A, owner decision B7)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.conftest import requires_db

from rental_agent.contracts import enums as e
from rental_agent.contracts.fakes import FakeLlmExecutor
from rental_agent.db.models import CommuteResult, Destination, ModelExecution, TransitStop
from rental_agent.enrichment.commute.research import (
    TASK_TYPE,
    CommuteResearchRejected,
    CommuteResearchService,
)

pytestmark = requires_db

GOOD_OUTPUT = {
    "duration_min_s": 1800,
    "duration_max_s": 2700,
    "likely_routes": ["A train"],
    "transfer_count": 1,
    "named_stations": ["Fulton St"],
    "summary": "Roughly 30-45 minutes via the A train.",
    "sources": [{"url": "https://example.test/transit-guide", "title": "Transit guide"}],
    "confidence": "MEDIUM",
}


@pytest.fixture()
def destination(db_session: Session) -> uuid.UUID:
    dest = Destination(
        destination_code=f"TEST_{uuid.uuid4().hex[:6]}",
        destination_type="UNIVERSITY_CAMPUS",
        display_name="Test Campus",
        routing_anchor_name="Main hall",
        routing_anchor_point="SRID=4326;POINT(-73.99 40.73)",
        registry_version="v1",
    )
    db_session.add(dest)
    db_session.commit()
    return dest.destination_id


def _service(db_session: Session, output: dict | None) -> CommuteResearchService:
    llm = FakeLlmExecutor(outputs={TASK_TYPE: output} if output is not None else {})
    return CommuteResearchService(db_session, llm, cache_days=14)


def test_research_persists_estimate_with_sources_and_expiry(
    db_session: Session, seeded_listing, destination
):
    service = _service(db_session, GOOD_OUTPUT)
    result = service.research(
        canonical_listing_id=seeded_listing,
        destination_id=destination,
        origin_description="100 Test St, Manhattan",
        input_location_hash="hash1",
    )
    db_session.commit()
    assert result.result_type == e.CommuteResultType.RESEARCHED_ESTIMATE.value
    assert result.sources and result.sources[0]["url"].startswith("https://")
    assert result.duration_min_s == 1800 and result.duration_max_s == 2700
    assert result.route_summary["label"] == "web-researched estimate"
    expected_expiry = datetime.now(tz=UTC) + timedelta(days=14)
    assert abs((result.expires_at - expected_expiry).total_seconds()) < 120
    # research execution is linked and auditable
    assert result.model_execution_id is not None
    assert db_session.get(ModelExecution, result.model_execution_id).task_type == TASK_TYPE
    # no transit dataset loaded -> honest UNABLE_TO_VALIDATE, never a fake pass
    assert result.validation_status == e.TransitValidationStatus.UNABLE_TO_VALIDATE.value


def test_memory_only_output_is_rejected(db_session: Session, seeded_listing, destination):
    no_sources = dict(GOOD_OUTPUT, sources=[])
    service = _service(db_session, no_sources)
    with pytest.raises(CommuteResearchRejected, match="sources"):
        service.research(
            canonical_listing_id=seeded_listing,
            destination_id=destination,
            origin_description="100 Test St",
            input_location_hash="hash1",
        )
    assert db_session.execute(select(func.count()).select_from(CommuteResult)).scalar() == 0


def test_fresh_result_is_reused_without_new_llm_call(
    db_session: Session, seeded_listing, destination
):
    llm = FakeLlmExecutor(outputs={TASK_TYPE: GOOD_OUTPUT})
    service = CommuteResearchService(db_session, llm, cache_days=14)
    first = service.research(
        canonical_listing_id=seeded_listing,
        destination_id=destination,
        origin_description="100 Test St",
        input_location_hash="hash1",
    )
    db_session.commit()
    second = service.research(
        canonical_listing_id=seeded_listing,
        destination_id=destination,
        origin_description="100 Test St",
        input_location_hash="hash1",
    )
    assert second.commute_result_id == first.commute_result_id
    assert len(llm.requests) == 1  # 14-day cache prevented a second call


def test_station_cross_check_against_local_transit_data(
    db_session: Session, seeded_listing, destination, seeded_source
):
    db_session.add(
        TransitStop(
            provider_source_id=seeded_source,
            provider_stop_id="A38",
            operator_code="MTA",
            stop_name="Fulton St",
            mode="SUBWAY",
            location_point="SRID=4326;POINT(-74.0077 40.7103)",
            active_status="ACTIVE",
            dataset_version="test-1",
        )
    )
    db_session.commit()
    service = _service(db_session, GOOD_OUTPUT)
    result = service.research(
        canonical_listing_id=seeded_listing,
        destination_id=destination,
        origin_description="100 Test St",
        input_location_hash="hash2",
    )
    # station matches; route "A train" is unmatched (no routes loaded) -> WARNING
    assert result.validation_status == e.TransitValidationStatus.WARNING.value
    assert result.validation_reasons["unmatched_stations"] == []


def test_database_rejects_researched_estimate_without_sources(
    db_session: Session, seeded_listing, destination
):
    from sqlalchemy.exc import IntegrityError

    bad = CommuteResult(
        canonical_listing_id=seeded_listing,
        destination_id=destination,
        result_type=e.CommuteResultType.RESEARCHED_ESTIMATE.value,
        time_basis="DEPART_AT",
        result_status="UNAVAILABLE",
        input_location_hash="h",
        destination_registry_version="v1",
        calculated_at=datetime.now(tz=UTC),
    )
    db_session.add(bad)
    with pytest.raises(IntegrityError, match="research_requires_sources"):
        db_session.commit()
    db_session.rollback()
