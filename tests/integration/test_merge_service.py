"""Manual merge/split workflow (02 §8.5; schema acceptance test 4; PR-ACQ-004)."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.conftest import requires_db

from rental_agent.canonical.merge_service import MergeError, MergeService
from rental_agent.canonical.selection_service import HumanActionRequired
from rental_agent.contracts import enums as e
from rental_agent.db.models import (
    Address,
    Building,
    CanonicalListing,
    CanonicalMerge,
    DuplicateCandidate,
    ListingEvent,
    ListingSourceLink,
    ReviewIssue,
)

pytestmark = requires_db

NOW = datetime.now(tz=UTC)


@pytest.fixture()
def two_listings(db_session: Session, seeded_source):
    """Two listings in one building, each with one source link, plus a PENDING
    duplicate candidate and its review issue (as normalization would create)."""
    from rental_agent.db.models import RefreshRun, SourceObservation, SourceRun

    address = Address(locality="New York", administrative_area="NY", formatted_address="1 Pair St")
    db_session.add(address)
    db_session.flush()
    building = Building(address_id=address.address_id)
    db_session.add(building)
    db_session.flush()

    run = RefreshRun(
        trigger_type="MANUAL",
        logical_run_key=f"test:{uuid.uuid4().hex}",
        started_at=NOW,
        pipeline_version="t1",
    )
    db_session.add(run)
    db_session.flush()
    source_run = SourceRun(
        refresh_run_id=run.refresh_run_id,
        source_id=seeded_source,
        started_at=NOW,
        adapter_version="t1",
    )
    db_session.add(source_run)
    db_session.flush()

    listings = []
    for i in range(2):
        listing = CanonicalListing(
            building_id=building.building_id,
            layout_class="ONE_BEDROOM",
            monthly_rent_minor=350000 + i * 1000,
            first_seen_at=NOW,
            last_seen_at=NOW,
            last_material_change_at=NOW,
        )
        db_session.add(listing)
        db_session.flush()
        observation = SourceObservation(
            source_id=seeded_source,
            source_run_id=source_run.source_run_id,
            source_native_id=f"N{i}",
            source_url=f"https://example.test/{i}",
            observed_at=NOW,
            retrieved_at=NOW,
            content_hash=f"h{i}",
            parsed_payload={},
            parse_status="VALID",
            contact_redaction_status="NOT_PRESENT",
            adapter_version="t1",
            schema_version="1.0.0",
        )
        db_session.add(observation)
        db_session.flush()
        db_session.add(
            ListingSourceLink(
                canonical_listing_id=listing.canonical_listing_id,
                source_id=seeded_source,
                source_native_id=f"N{i}",
                source_url=f"https://example.test/{i}",
                first_observation_id=observation.source_observation_id,
                latest_observation_id=observation.source_observation_id,
                first_seen_at=NOW,
                last_seen_at=NOW,
                link_status="ACTIVE",
                identity_method="SOURCE_NATIVE_CONTINUITY",
                identity_confidence="HIGH",
                identity_rule_version="t1",
            )
        )
        listings.append(listing)
    a, b = listings
    a_id, b_id = sorted((a.canonical_listing_id, b.canonical_listing_id), key=str)
    candidate = DuplicateCandidate(
        listing_a_id=a_id,
        listing_b_id=b_id,
        evidence={"rule": "test"},
        rule_version="t1",
        status="PENDING",
    )
    db_session.add(candidate)
    db_session.flush()
    db_session.add(
        ReviewIssue(
            entity_type="LISTING",
            entity_id=a_id,
            issue_type="DUPLICATE_CANDIDATE",
            severity="WARNING",
            details={"duplicate_candidate_id": str(candidate.duplicate_candidate_id)},
        )
    )
    db_session.commit()
    return a_id, b_id, candidate.duplicate_candidate_id


def test_manual_merge_moves_links_and_preserves_history(db_session: Session, two_listings):
    a_id, b_id, _ = two_listings
    service = MergeService(db_session)
    merge = service.merge_listings(
        source_listing_id=b_id,
        target_listing_id=a_id,
        actor="local_operator",
        actor_type=e.ActorType.HUMAN,
    )
    db_session.commit()

    source = db_session.get(CanonicalListing, b_id)
    target = db_session.get(CanonicalListing, a_id)
    assert source.lifecycle_status == "MERGED"  # retained, not deleted
    assert target.lifecycle_status != "MERGED"
    links = db_session.execute(select(ListingSourceLink)).scalars().all()
    assert all(link.canonical_listing_id == a_id for link in links)
    assert len(links) == 2
    event = db_session.execute(
        select(ListingEvent).where(ListingEvent.event_type == "MERGED")
    ).scalar_one()
    assert event.canonical_listing_id == b_id
    assert merge.evidence["moved_link_ids"]


def test_system_actor_cannot_manual_merge(db_session: Session, two_listings):
    a_id, b_id, _ = two_listings
    with pytest.raises(HumanActionRequired):
        MergeService(db_session).merge_listings(
            source_listing_id=b_id,
            target_listing_id=a_id,
            actor="pipeline",
            actor_type=e.ActorType.SYSTEM,
        )


def test_cannot_merge_into_merged_target(db_session: Session, two_listings):
    a_id, b_id, _ = two_listings
    service = MergeService(db_session)
    service.merge_listings(
        source_listing_id=b_id,
        target_listing_id=a_id,
        actor="local_operator",
        actor_type=e.ActorType.HUMAN,
    )
    db_session.commit()
    address = Address(locality="NY", administrative_area="NY", formatted_address="2 Other St")
    db_session.add(address)
    db_session.flush()
    building = Building(address_id=address.address_id)
    db_session.add(building)
    db_session.flush()
    third = CanonicalListing(
        building_id=building.building_id,
        first_seen_at=NOW,
        last_seen_at=NOW,
        last_material_change_at=NOW,
    )
    db_session.add(third)
    db_session.flush()
    with pytest.raises(MergeError, match="itself merged"):
        service.merge_listings(
            source_listing_id=third.canonical_listing_id,
            target_listing_id=b_id,  # b was merged away
            actor="local_operator",
            actor_type=e.ActorType.HUMAN,
        )


def test_confirm_duplicate_merges_and_resolves_issue(db_session: Session, two_listings):
    a_id, b_id, candidate_id = two_listings
    service = MergeService(db_session)
    candidate = service.resolve_duplicate_candidate(
        candidate_id,
        confirmed_duplicate=True,
        actor="local_operator",
        actor_type=e.ActorType.HUMAN,
        survivor_listing_id=a_id,
    )
    db_session.commit()
    assert candidate.status == "CONFIRMED_DUPLICATE"
    assert candidate.resolved_by == "local_operator"
    assert db_session.get(CanonicalListing, b_id).lifecycle_status == "MERGED"
    issue = db_session.execute(select(ReviewIssue)).scalar_one()
    assert issue.status == "RESOLVED"
    assert db_session.execute(select(func.count()).select_from(CanonicalMerge)).scalar() == 1


def test_confirm_distinct_is_durable(db_session: Session, two_listings):
    a_id, b_id, candidate_id = two_listings
    service = MergeService(db_session)
    candidate = service.resolve_duplicate_candidate(
        candidate_id,
        confirmed_duplicate=False,
        actor="local_operator",
        actor_type=e.ActorType.HUMAN,
    )
    db_session.commit()
    assert candidate.status == "CONFIRMED_DISTINCT"
    # Nothing merged; both listings intact.
    assert db_session.get(CanonicalListing, a_id).lifecycle_status != "MERGED"
    assert db_session.get(CanonicalListing, b_id).lifecycle_status != "MERGED"
    # A second resolution attempt is rejected — the decision stands.
    with pytest.raises(MergeError, match="already resolved"):
        service.resolve_duplicate_candidate(
            candidate_id,
            confirmed_duplicate=True,
            actor="local_operator",
            actor_type=e.ActorType.HUMAN,
        )


def test_reverse_merge_restores_links_for_review(db_session: Session, two_listings):
    a_id, b_id, _ = two_listings
    service = MergeService(db_session)
    merge = service.merge_listings(
        source_listing_id=b_id,
        target_listing_id=a_id,
        actor="local_operator",
        actor_type=e.ActorType.HUMAN,
    )
    db_session.commit()
    service.reverse_merge(
        merge.canonical_merge_id,
        actor="local_operator",
        actor_type=e.ActorType.HUMAN,
        reason="wrong pair",
    )
    db_session.commit()
    restored = db_session.get(CanonicalListing, b_id)
    assert restored.lifecycle_status == "REVIEW_REQUIRED"  # human decides next state
    b_links = db_session.execute(
        select(func.count())
        .select_from(ListingSourceLink)
        .where(ListingSourceLink.canonical_listing_id == b_id)
    ).scalar()
    assert b_links == 1
    assert db_session.get(CanonicalMerge, merge.canonical_merge_id).reversed_at is not None
