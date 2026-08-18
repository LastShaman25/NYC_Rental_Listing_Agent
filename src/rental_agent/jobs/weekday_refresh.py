"""Weekday refresh coordinator (06 §9–11; Phase 7).

One command runs the full local pipeline once, idempotently per local day:

    uv run --no-sync python -m rental_agent.jobs.weekday_refresh

Stages: acquisition (StreetEasy via Tavily) → normalization jobs → geocoding →
boundary scope validation → nearby-transit candidates → usefulness → admission.
Windows Task Scheduler owns the recurring 6:00 AM cadence (see
scripts/schedule/); this module never self-schedules, and duplicate triggers on
the same day join the existing logical run (06 §9.4).

Commute research stays on-demand (B7) — it is NOT part of this pipeline.
Disappearance processing is structurally disabled for search-discovered scope.
"""

import sys
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from rental_agent.acquisition.adapters.streeteasy_search import StreetEasySearchAdapter
from rental_agent.acquisition.runner import AcquisitionRunner, drain_normalize_jobs
from rental_agent.acquisition.search_tavily import build_search_provider_from_settings
from rental_agent.canonical.admission import AdmissionService
from rental_agent.config.logging import configure_logging, get_logger
from rental_agent.config.settings import load_settings
from rental_agent.contracts import enums as e
from rental_agent.db.engine import build_engine, build_session_factory
from rental_agent.enrichment.location.boundaries import validate_boundaries
from rental_agent.enrichment.location.geocoders import CensusGeocoder, NycGeosearchGeocoder
from rental_agent.enrichment.location.service import GeocodeService
from rental_agent.enrichment.transit.nearby import NearbyTransitService
from rental_agent.enrichment.transit.usefulness import classify_usefulness

log = get_logger(__name__)

SCHEDULE_VERSION = "v1"

# Listing-graph tables purged on a manual full re-acquisition (owner decision
# 2026-08-18: "completely discard the old data"). CASCADE pulls in every
# FK-dependent (buildings, units, links, events, transit access, selections,
# shortlist ENTRIES, media associations...). Deliberately preserved: sources,
# client presets/profiles, destinations, transit stops/routes, boundaries,
# run history, model-execution audit.
_DISCARD_TABLES = (
    "app.address",
    "app.canonical_listing",
    "raw.source_observation",
    "app.media_asset",
    "app.fact_assertion",
    "app.fact_resolution",
    "app.review_issue",
    "app.human_override",
    "ops.job",
)


def discard_inventory(factory) -> None:
    """Wipe the listing graph before a fresh manual acquisition."""
    from sqlalchemy import text as sql_text

    with factory() as session:
        before = session.execute(
            sql_text("SELECT count(*) FROM app.canonical_listing")
        ).scalar()
        session.execute(sql_text(f"TRUNCATE {', '.join(_DISCARD_TABLES)} CASCADE"))
        session.commit()
    log.info("inventory_discarded", listings_discarded=before)
    print(f"discarded {before} existing listings (fresh re-acquisition)")


def run_weekday_refresh(
    trigger: e.RefreshTriggerType = e.RefreshTriggerType.SCHEDULED,
    logical_key: str | None = None,
) -> int:
    settings = load_settings()
    configure_logging(settings.paths.logs)
    factory = build_session_factory(build_engine(settings))

    local_date = datetime.now(tz=ZoneInfo(settings.timezone)).date()
    if logical_key is None:
        logical_key = f"weekday_inventory_refresh:{local_date}:{SCHEDULE_VERSION}"
    log.info("refresh_start", key=logical_key, trigger=trigger.value)

    from rental_agent.acquisition.adapters.apartments_com_search import (
        ApartmentsComSearchAdapter,
    )
    from rental_agent.contracts.providers import SourceAdapter

    if trigger is e.RefreshTriggerType.MANUAL:
        # Owner decision 2026-08-18: a manual full re-acquisition always
        # starts from a clean slate.
        discard_inventory(factory)

    from rental_agent.acquisition.adapters.rent_com_search import RentComSearchAdapter

    search_provider = build_search_provider_from_settings(settings)
    adapters: list[SourceAdapter] = [
        StreetEasySearchAdapter(search_provider, max_results_per_query=15),
        # Second source (owner decision 2026-08-18): Fort Lee coverage.
        ApartmentsComSearchAdapter(search_provider, max_results_per_query=15),
        # Third source (owner decision 2026-08-18): extract-friendly NJ
        # coverage with Jersey City sub-area partitions.
        RentComSearchAdapter(search_provider, max_results_per_query=15),
    ]
    acquisitions = [
        AcquisitionRunner(factory).run_source(
            adapter,
            logical_run_key=logical_key,
            trigger_type=trigger,
            discovery_method=e.DiscoveryMethod.SEARCH_INDEX,
        )
        for adapter in adapters
    ]
    total_discovered = sum(a.discovered for a in acquisitions)
    total_new = sum(a.persisted_new for a in acquisitions)
    normalized = drain_normalize_jobs(factory, discovery_method=e.DiscoveryMethod.SEARCH_INDEX)

    with factory() as session:
        geocode = GeocodeService(
            session, [NycGeosearchGeocoder(), CensusGeocoder()]
        ).geocode_pending()
        session.commit()
    with factory() as session:
        scope = validate_boundaries(session)
        session.commit()
    with factory() as session:
        transit = NearbyTransitService(session).enrich_all_geocoded()
        usefulness = classify_usefulness(session)
        session.commit()
    with factory() as session:
        admission = AdmissionService(session).evaluate_candidates()
        session.commit()

    # A manual full re-acquisition starts from a wiped inventory, so it also
    # re-runs detail enrichment automatically (owner expectation 2026-08-18:
    # one button yields a complete, page-verified inventory). Scheduled runs
    # keep enrichment incremental via the weekday cadence.
    enrichment_counts: dict[str, int] = {}
    if trigger is e.RefreshTriggerType.MANUAL:
        from rental_agent.jobs.detail_enrichment import run_detail_enrichment

        enrichment_counts = run_detail_enrichment()

    # Finalize the refresh-run record honestly (06 §10.2).
    with factory() as session:
        from rental_agent.db.repositories.runs import RefreshRunRepository

        runs = RefreshRunRepository(session)
        run_id, _ = runs.create_or_join(
            logical_run_key=logical_key,
            trigger_type=trigger,
            started_at=datetime.now(tz=UTC),
            pipeline_version="0.2.0",
        )
        status = (
            e.RefreshRunStatus.SUCCEEDED
            if all(a.status is e.SourceRunStatus.HEALTHY for a in acquisitions)
            else e.RefreshRunStatus.PARTIAL_SUCCESS
        )
        runs.set_status(
            run_id,
            status,
            completed_at=datetime.now(tz=UTC),
            summary_counts={
                "discovered": total_discovered,
                "persisted_new": total_new,
                "normalized": normalized,
                "geocoded": geocode.geocoded,
                "scope_evaluated": scope.evaluated,
                "transit_rows": transit.access_rows_created,
                "useful_options": usefulness.useful,
                "activated": admission.activated,
                "excluded": admission.excluded,
                **(
                    {"enriched": enrichment_counts.get("ENRICHED", 0)}
                    if enrichment_counts
                    else {}
                ),
            },
        )
        session.commit()

    log.info(
        "refresh_complete",
        status=status.value,
        discovered=total_discovered,
        new=total_new,
        normalized=normalized,
        geocoded=geocode.geocoded,
        activated=admission.activated,
        excluded=admission.excluded,
    )
    print(
        f"refresh {status.value}: discovered={total_discovered} "
        f"new={total_new} normalized={normalized} "
        f"geocoded={geocode.geocoded} activated={admission.activated} "
        f"excluded={admission.excluded}"
    )
    return 0 if status is not e.RefreshRunStatus.FAILED else 1


if __name__ == "__main__":
    if "--manual" in sys.argv:
        # Manual re-acquisition gets its own run key so it truly re-runs even
        # after the scheduled run already succeeded today (owner 2026-08-18).
        stamp = datetime.now(tz=UTC).strftime("%Y-%m-%d_%H%M%S")
        raise SystemExit(
            run_weekday_refresh(
                e.RefreshTriggerType.MANUAL, logical_key=f"manual_refresh:{stamp}"
            )
        )
    raise SystemExit(run_weekday_refresh(e.RefreshTriggerType.SCHEDULED))
