"""Disappearance gating, thresholds, and the circuit breaker (06 §16, §24.4)."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.conftest import requires_db

from rental_agent.canonical.disappearance import DisappearanceService
from rental_agent.db.models import (
    Address,
    Building,
    CanonicalListing,
    HumanOverride,
    ListingSourceLink,
    RefreshRun,
    ReviewIssue,
    SourceObservation,
    SourceRun,
)

pytestmark = requires_db

NOW = datetime.now(tz=UTC)
OLD = NOW - timedelta(hours=48)  # beyond the 36h removal threshold


def _source_run(db_session, source_id, *, gate: bool, started=NOW) -> SourceRun:
    run = RefreshRun(
        trigger_type="SCHEDULED",
        logical_run_key=f"t:{uuid.uuid4().hex}",
        started_at=started,
        pipeline_version="t",
    )
    db_session.add(run)
    db_session.flush()
    source_run = SourceRun(
        refresh_run_id=run.refresh_run_id,
        source_id=source_id,
        started_at=started,
        adapter_version="t",
        status="HEALTHY" if gate else "DEGRADED",
        health_gate_passed=gate,
    )
    db_session.add(source_run)
    db_session.flush()
    return source_run


def _listing_with_link(
    db_session, source_id, source_run, *, last_seen=OLD, lifecycle="ACTIVE"
) -> tuple[CanonicalListing, ListingSourceLink]:
    address = Address(
        locality="NY", administrative_area="NY", formatted_address=f"a-{uuid.uuid4().hex[:6]}"
    )
    db_session.add(address)
    db_session.flush()
    building = Building(address_id=address.address_id)
    db_session.add(building)
    db_session.flush()
    listing = CanonicalListing(
        building_id=building.building_id,
        layout_class="ONE_BEDROOM",
        lifecycle_status=lifecycle,
        first_seen_at=last_seen,
        last_seen_at=last_seen,
        last_material_change_at=last_seen,
    )
    db_session.add(listing)
    db_session.flush()
    observation = SourceObservation(
        source_id=source_id,
        source_run_id=source_run.source_run_id,
        source_native_id=uuid.uuid4().hex[:8],
        source_url=f"https://d.test/{uuid.uuid4().hex[:8]}",
        observed_at=last_seen,
        retrieved_at=last_seen,
        content_hash=uuid.uuid4().hex,
        parsed_payload={},
        parse_status="VALID",
        contact_redaction_status="NOT_PRESENT",
        adapter_version="t",
        schema_version="1",
    )
    db_session.add(observation)
    db_session.flush()
    link = ListingSourceLink(
        canonical_listing_id=listing.canonical_listing_id,
        source_id=source_id,
        source_native_id=observation.source_native_id,
        source_url=observation.source_url,
        first_observation_id=observation.source_observation_id,
        latest_observation_id=observation.source_observation_id,
        first_seen_at=last_seen,
        last_seen_at=last_seen,
        link_status="ACTIVE",
        identity_method="SOURCE_NATIVE_CONTINUITY",
        identity_confidence="HIGH",
        identity_rule_version="t",
    )
    db_session.add(link)
    db_session.commit()
    return listing, link


def test_unhealthy_run_is_refused(db_session: Session, seeded_source):
    old_run = _source_run(db_session, seeded_source, gate=True, started=OLD)
    _listing_with_link(db_session, seeded_source, old_run)
    degraded = _source_run(db_session, seeded_source, gate=False)
    summary = DisappearanceService(db_session).process_source_run(degraded.source_run_id)
    assert summary.refused_reason == "health_gate_not_passed"
    assert summary.links_marked_missing == 0


def test_one_healthy_miss_marks_missing_not_inactive(db_session: Session, seeded_source):
    old_run = _source_run(db_session, seeded_source, gate=True, started=OLD)
    listing, link = _listing_with_link(db_session, seeded_source, old_run)
    healthy = _source_run(db_session, seeded_source, gate=True)
    summary = DisappearanceService(db_session).process_source_run(healthy.source_run_id)
    db_session.commit()
    assert summary.links_marked_missing == 1
    db_session.refresh(link)
    db_session.refresh(listing)
    assert link.link_status == "MISSING"
    assert listing.lifecycle_status == "ACTIVE"  # one miss never inactivates


def test_two_healthy_misses_plus_36h_removes_and_inactivates(db_session: Session, seeded_source):
    old_run = _source_run(db_session, seeded_source, gate=True, started=OLD)
    listing, link = _listing_with_link(db_session, seeded_source, old_run)
    service = DisappearanceService(db_session)
    first = _source_run(db_session, seeded_source, gate=True, started=NOW - timedelta(hours=20))
    service.process_source_run(first.source_run_id)
    db_session.commit()
    second = _source_run(db_session, seeded_source, gate=True)
    summary = service.process_source_run(second.source_run_id)
    db_session.commit()
    assert summary.links_removed == 1
    assert summary.listings_inactivated == 1
    db_session.refresh(link)
    db_session.refresh(listing)
    assert link.link_status == "REMOVED"
    assert listing.lifecycle_status == "INACTIVE"
    assert listing.inactive_at is not None


def test_active_lifecycle_override_blocks_inactivation(db_session: Session, seeded_source):
    old_run = _source_run(db_session, seeded_source, gate=True, started=OLD)
    listing, _ = _listing_with_link(db_session, seeded_source, old_run)
    db_session.add(
        HumanOverride(
            entity_type="LISTING",
            entity_id=listing.canonical_listing_id,
            field_name="lifecycle_status",
            override_value={"value": "ACTIVE"},
            reason_code="SOURCE_ERROR",
            reason_text="keep active; verified by phone-free site visit",
            created_by="local_operator",
        )
    )
    db_session.commit()
    service = DisappearanceService(db_session)
    for hours in (20, 0):
        run = _source_run(
            db_session, seeded_source, gate=True, started=NOW - timedelta(hours=hours)
        )
        service.process_source_run(run.source_run_id)
        db_session.commit()
    db_session.refresh(listing)
    assert listing.lifecycle_status == "ACTIVE"  # override outranks disappearance


def test_mass_inactivation_circuit_breaker(db_session: Session, seeded_source):
    old_run = _source_run(db_session, seeded_source, gate=True, started=OLD)
    listings = [_listing_with_link(db_session, seeded_source, old_run)[0] for _ in range(6)]
    # Only 4 ACTIVE listings total means the 25% cap is 1 — 6 proposals must trip.
    service = DisappearanceService(db_session)
    first = _source_run(db_session, seeded_source, gate=True, started=NOW - timedelta(hours=20))
    service.process_source_run(first.source_run_id)
    db_session.commit()
    second = _source_run(db_session, seeded_source, gate=True)
    summary = service.process_source_run(second.source_run_id)
    db_session.commit()
    assert summary.breaker_tripped is True
    assert summary.listings_inactivated == 0  # nothing applied
    for listing in listings:
        db_session.refresh(listing)
        assert listing.lifecycle_status == "ACTIVE"
    issue = db_session.execute(
        select(ReviewIssue).where(ReviewIssue.severity == "BLOCKING")
    ).scalar_one()
    assert issue.details["reason"] == "mass_inactivation_circuit_breaker"
