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


def run_weekday_refresh(trigger: e.RefreshTriggerType = e.RefreshTriggerType.SCHEDULED) -> int:
    settings = load_settings()
    configure_logging(settings.paths.logs)
    factory = build_session_factory(build_engine(settings))

    local_date = datetime.now(tz=ZoneInfo(settings.timezone)).date()
    logical_key = f"weekday_inventory_refresh:{local_date}:{SCHEDULE_VERSION}"
    log.info("refresh_start", key=logical_key, trigger=trigger.value)

    adapter = StreetEasySearchAdapter(
        build_search_provider_from_settings(settings), max_results_per_query=15
    )
    acquisition = AcquisitionRunner(factory).run_source(
        adapter,
        logical_run_key=logical_key,
        trigger_type=trigger,
        discovery_method=e.DiscoveryMethod.SEARCH_INDEX,
    )
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
            if acquisition.status is e.SourceRunStatus.HEALTHY
            else e.RefreshRunStatus.PARTIAL_SUCCESS
        )
        runs.set_status(
            run_id,
            status,
            completed_at=datetime.now(tz=UTC),
            summary_counts={
                "discovered": acquisition.discovered,
                "persisted_new": acquisition.persisted_new,
                "normalized": normalized,
                "geocoded": geocode.geocoded,
                "scope_evaluated": scope.evaluated,
                "transit_rows": transit.access_rows_created,
                "useful_options": usefulness.useful,
                "activated": admission.activated,
                "excluded": admission.excluded,
            },
        )
        session.commit()

    log.info(
        "refresh_complete",
        status=status.value,
        discovered=acquisition.discovered,
        new=acquisition.persisted_new,
        normalized=normalized,
        geocoded=geocode.geocoded,
        activated=admission.activated,
        excluded=admission.excluded,
    )
    print(
        f"refresh {status.value}: discovered={acquisition.discovered} "
        f"new={acquisition.persisted_new} normalized={normalized} "
        f"geocoded={geocode.geocoded} activated={admission.activated} "
        f"excluded={admission.excluded}"
    )
    return 0 if status is not e.RefreshRunStatus.FAILED else 1


if __name__ == "__main__":
    trigger = (
        e.RefreshTriggerType.MANUAL if "--manual" in sys.argv else e.RefreshTriggerType.SCHEDULED
    )
    raise SystemExit(run_weekday_refresh(trigger))
