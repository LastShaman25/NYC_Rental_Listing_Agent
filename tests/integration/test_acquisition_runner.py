"""End-to-end fixture slice: search discovery → observations → jobs → canonical (Phase 2 gate)."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker
from tests.conftest import requires_db

from rental_agent.acquisition.adapters.streeteasy_search import StreetEasySearchAdapter
from rental_agent.acquisition.runner import AcquisitionRunner, drain_normalize_jobs
from rental_agent.contracts import enums as e
from rental_agent.contracts.fakes import FakeSearchProvider
from rental_agent.contracts.providers import SearchResponse, SearchResultItem
from rental_agent.db.models import (
    AdapterCheckpoint,
    CanonicalListing,
    Job,
    ListingSourceLink,
    Source,
    SourceObservation,
    SourceRun,
)

pytestmark = requires_db

FIXTURE_ITEMS = [
    SearchResultItem(
        url="https://streeteasy.com/building/alpha-tower/9c",
        title="Alpha Tower #9C - 1 bed at 400 West 20th Street",
        snippet="1 bedroom / 1 bath, $3,800/month in Chelsea, Manhattan.",
        rank=1,
    ),
    SearchResultItem(
        url="https://streeteasy.com/rental/1234567",
        title="Sunny studio at 88 Court Street",
        snippet="Studio apartment for $2,650 per month in Brooklyn Heights.",
        rank=2,
    ),
]


@pytest.fixture()
def factory(db_engine) -> sessionmaker[Session]:
    return sessionmaker(bind=db_engine, expire_on_commit=False)


@pytest.fixture()
def registered_streeteasy(factory) -> None:
    with factory() as session:
        session.add(
            Source(
                source_code="streeteasy",
                display_name="StreetEasy",
                source_type="LISTING",
                access_method="OTHER_APPROVED",
                approval_status="APPROVED",
                enabled=True,
                policy_version="search-index-1",
            )
        )
        session.commit()


def _fixture_adapter(items=None) -> StreetEasySearchAdapter:
    provider = FakeSearchProvider()
    adapter = StreetEasySearchAdapter(provider)
    for partition in adapter.plan_partitions({}):
        provider.responses[partition.query_parameters["query"]] = SearchResponse(
            status=e.ProviderRequestStatus.SUCCEEDED,
            items=items if items is not None else FIXTURE_ITEMS,
        )
    return adapter


def _run(factory, adapter, key="run:1") -> object:
    return AcquisitionRunner(factory).run_source(
        adapter,
        logical_run_key=key,
        trigger_type=e.RefreshTriggerType.MANUAL,
        discovery_method=e.DiscoveryMethod.SEARCH_INDEX,
    )


def test_full_slice_discovery_to_canonical(factory, registered_streeteasy):
    summary = _run(factory, _fixture_adapter())
    assert summary.status is e.SourceRunStatus.HEALTHY
    assert summary.persisted_new == 2  # two unique listings across all partitions
    assert summary.duplicates_skipped > 0  # same items returned per partition
    assert summary.partitions_completed == 27  # 9 geo partitions x 3 layouts

    drained = drain_normalize_jobs(factory, discovery_method=e.DiscoveryMethod.SEARCH_INDEX)
    assert drained == 2

    with factory() as session:
        listings = session.execute(select(CanonicalListing)).scalars().all()
        assert len(listings) == 2
        rents = sorted(listing.monthly_rent_minor for listing in listings)
        assert rents == [265000, 380000]
        links = session.execute(select(ListingSourceLink)).scalars().all()
        assert all(link.discovery_method == "SEARCH_INDEX" for link in links)
        jobs = session.execute(select(Job)).scalars().all()
        assert all(job.status == "SUCCEEDED" for job in jobs)


def test_search_run_never_passes_disappearance_gate(factory, registered_streeteasy):
    summary = _run(factory, _fixture_adapter())
    assert summary.status is e.SourceRunStatus.HEALTHY
    assert summary.health_gate_passed is False  # B3: search absence is not evidence
    with factory() as session:
        row = session.get(SourceRun, summary.source_run_id)
        assert row.health_gate_passed is False
        assert row.counts["discovery_method"] == "SEARCH_INDEX"


def test_rerun_updates_freshness_without_canonical_duplication(factory, registered_streeteasy):
    _run(factory, _fixture_adapter(), key="run:1")
    drain_normalize_jobs(factory, discovery_method=e.DiscoveryMethod.SEARCH_INDEX)
    summary2 = _run(factory, _fixture_adapter(), key="run:2")
    drained2 = drain_normalize_jobs(factory, discovery_method=e.DiscoveryMethod.SEARCH_INDEX)
    # A later run re-observes both listings (new observation rows, PR-ACQ-002),
    # but unchanged content produces no new canonical listings or events.
    assert summary2.persisted_new == 2
    assert drained2 == 2
    with factory() as session:
        from rental_agent.db.models import ListingEvent

        assert session.execute(select(func.count()).select_from(CanonicalListing)).scalar() == 2
        assert session.execute(select(func.count()).select_from(SourceObservation)).scalar() == 4
        events = session.execute(select(ListingEvent)).scalars().all()
        assert sorted(ev.event_type for ev in events) == ["CREATED", "CREATED"]


def test_failed_search_provider_degrades_run(factory, registered_streeteasy):
    adapter = StreetEasySearchAdapter(FakeSearchProvider())  # all queries fail
    summary = _run(factory, adapter)
    assert summary.status is e.SourceRunStatus.DEGRADED
    assert summary.health_gate_passed is False
    assert summary.persisted_new == 0
    with factory() as session:
        # No canonical damage from a failed discovery run.
        assert session.execute(select(func.count()).select_from(CanonicalListing)).scalar() == 0


def test_unregistered_source_cannot_run(factory):
    with pytest.raises(LookupError, match="not registered"):
        _run(factory, _fixture_adapter())


def test_checkpoints_recorded_per_partition(factory, registered_streeteasy):
    summary = _run(factory, _fixture_adapter())
    with factory() as session:
        checkpoints = (
            session.execute(
                select(AdapterCheckpoint).where(
                    AdapterCheckpoint.source_run_id == summary.source_run_id
                )
            )
            .scalars()
            .all()
        )
        assert len(checkpoints) == 27
        assert all(cp.completed for cp in checkpoints)
