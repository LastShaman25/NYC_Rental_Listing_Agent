"""Availability check over the company property portfolio.

Run: uv run --no-sync python -m rental_agent.jobs.company_refresh [--force]

Checks every company property whose last check is missing, failed, or stale
(>1 day); ``--force`` rechecks everything. Dead file links are repaired via
the building's official website or StreetEasy search (see
enrichment.company.service). Commits per property — one failure never rolls
back the rest.
"""

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select

from rental_agent.config.logging import configure_logging, get_logger
from rental_agent.config.settings import load_settings
from rental_agent.db.engine import build_engine, build_session_factory
from rental_agent.db.models import CompanyProperty
from rental_agent.enrichment.company.service import CompanyAvailabilityService
from rental_agent.enrichment.listing_content.service import TavilyExtractClient
from rental_agent.enrichment.llm.openai_executor import executor_from_settings
from rental_agent.enrichment.location.geocoders import CensusGeocoder, NycGeosearchGeocoder

log = get_logger(__name__)

STALE_AFTER = timedelta(days=1)

# Owner request 2026-08-30: commute analysis runs during check/re-check and
# picks destinations automatically — the nearest anchor of EACH type
# (nearest school + nearest major destination), chosen by PostGIS distance
# exactly like the transit panel picks stations. Every geocoded property
# gets researched; the 14-day cache makes repeat checks free.
COMMUTE_DESTINATIONS_PER_TYPE = 1

# Live progress for the Company page's condition indicator (owner request
# 2026-08-29): the detached job publishes its state here; the web UI polls
# /api/company/status which reads it back. File-based on purpose — the job
# is a separate process and everything stays local.
STATUS_FILENAME = "company_refresh_status.json"


def status_path(logs_dir: Path | str | None = None) -> Path:
    return Path(logs_dir if logs_dir is not None else Path("local_data") / "logs") / (
        STATUS_FILENAME
    )


def write_status(path: Path, **payload: Any) -> None:
    """Best-effort atomic publish; a status hiccup never breaks the job."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload["updated_at"] = datetime.now(tz=UTC).isoformat()
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        log.warning("company_status_write_failed", error=str(exc))


def _research_company_commutes(session, llm, prop, cache_days: int) -> int:
    """Research commutes for a checked, geocoded company property to the
    nearest destination of each type (school + major destination). Returns
    fresh researches done (cached results cost nothing)."""
    from sqlalchemy import text as sql_text

    from rental_agent.enrichment.commute.research import (
        CommuteResearchRejected,
        CommuteResearchService,
    )

    if prop.latitude is None or prop.longitude is None:
        return 0
    destination_ids = list(
        session.execute(
            sql_text(
                "SELECT destination_id FROM ("
                "  SELECT destination_id, ROW_NUMBER() OVER ("
                "    PARTITION BY destination_type "
                "    ORDER BY ST_Distance(routing_anchor_point, "
                "      ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography)"
                "  ) AS rn FROM app.destination WHERE active"
                ") ranked WHERE rn <= :per_type"
            ),
            {
                "lon": prop.longitude,
                "lat": prop.latitude,
                "per_type": COMMUTE_DESTINATIONS_PER_TYPE,
            },
        ).scalars()
    )
    service = CommuteResearchService(session, llm, cache_days=cache_days)
    researched = 0
    for destination_id in destination_ids:
        if service.get_fresh_result(None, destination_id, prop.company_property_id):
            continue
        try:
            service.research(
                company_property_id=prop.company_property_id,
                destination_id=destination_id,
                origin_description=(
                    f"{prop.address_text or prop.name}, {prop.locality or 'New York'}"
                ),
                input_location_hash=(
                    f"company:{prop.company_property_id}:"
                    f"{prop.latitude:.5f},{prop.longitude:.5f}"
                ),
            )
            researched += 1
        except (CommuteResearchRejected, LookupError) as exc:
            log.warning(
                "company_commute_rejected", name=prop.name, error=str(exc)
            )
    return researched


def run_company_refresh(
    *, force: bool = False, failed_only: bool = False, commutes_only: bool = False
) -> dict[str, int]:
    settings = load_settings()
    status_file = status_path(settings.paths.logs)
    if commutes_only:
        mode = "commutes_only"
    else:
        mode = "failed_only" if failed_only else ("force" if force else "all")
    try:
        llm = executor_from_settings(settings.providers)
    except ValueError:
        log.error("company_refresh_missing_llm_key")
        write_status(
            status_file,
            state="failed",
            mode=mode,
            error="LLM API key missing (Settings → LLM API)",
        )
        return {"MISSING_KEYS": 1}
    from rental_agent.enrichment.transit.walking import OsrmFootRouter

    walk_router = OsrmFootRouter()
    extract_client = None
    search_provider = None
    if not commutes_only:
        # Page checks need Tavily; commute research needs only the LLM.
        search_key = settings.providers.search_provider_api_key
        if search_key is None:
            log.error("company_refresh_missing_search_key")
            write_status(
                status_file, state="failed", mode=mode, error="Tavily search API key missing"
            )
            return {"MISSING_KEYS": 1}
        from rental_agent.acquisition.search_tavily import TavilySearchProvider

        extract_client = TavilyExtractClient(search_key.get_secret_value())
        search_provider = TavilySearchProvider(search_key.get_secret_value())
    factory = build_session_factory(build_engine(settings))

    cutoff = datetime.now(tz=UTC) - STALE_AFTER
    with factory() as session:
        query = select(CompanyProperty.company_property_id).order_by(CompanyProperty.name)
        if failed_only:
            # Only rows whose last check failed (or never ran).
            query = query.where(CompanyProperty.check_status != "CHECKED")
        ids = list(session.execute(query).scalars())
    log.info("company_refresh_start", properties=len(ids), force=force, failed_only=failed_only)
    write_status(status_file, state="running", mode=mode, total=len(ids), done=0, counts={})

    counts: dict[str, int] = {}
    for index, property_id in enumerate(ids, start=1):
        with factory() as session:
            prop = session.get(CompanyProperty, property_id)
            if prop is None:
                continue
            write_status(
                status_file,
                state="running",
                mode=mode,
                total=len(ids),
                done=index - 1,
                counts=counts,
                current=prop.name,
            )
            if commutes_only:
                # Commute research + routed transit only (no Tavily involved)
                # — automatic for checked, geocoded properties.
                from rental_agent.enrichment.company.service import attach_nearby_transit

                try:
                    if (
                        prop.availability is not None
                        and "nearby_transit" not in prop.availability
                    ):
                        routed = attach_nearby_transit(session, prop, walk_router)
                        if routed:
                            counts["TRANSIT_ROUTED"] = (
                                counts.get("TRANSIT_ROUTED", 0) + routed
                            )
                    researched = _research_company_commutes(
                        session,
                        llm,
                        prop,
                        settings.providers.commute_research_cache_days,
                    )
                    session.commit()
                    if researched:
                        counts["COMMUTES"] = counts.get("COMMUTES", 0) + researched
                except Exception as exc:  # noqa: BLE001 - batch keeps going
                    session.rollback()
                    log.error(
                        "company_commute_error", property=str(property_id), error=str(exc)
                    )
                    counts["ERROR"] = counts.get("ERROR", 0) + 1
                continue
            fresh = (
                not force
                and prop.check_status == "CHECKED"
                and prop.last_checked_at is not None
                and prop.last_checked_at >= cutoff
            )
            if fresh:
                counts["SKIPPED_FRESH"] = counts.get("SKIPPED_FRESH", 0) + 1
                continue
            assert extract_client is not None  # built for every non-commutes mode
            service = CompanyAvailabilityService(
                session,
                llm,
                extract_client,
                search_provider=search_provider,
                geocoders=[NycGeosearchGeocoder(), CensusGeocoder()],
                walk_router=walk_router,
            )
            try:
                # Only a full "Re-check all" (force) discards previous
                # snapshots on failure (owner decision 2026-08-30).
                status = service.check(prop, discard_stale=force)
                session.commit()
            except Exception as exc:  # noqa: BLE001 - batch keeps going
                session.rollback()
                log.error("company_refresh_error", property=str(property_id), error=str(exc))
                counts["ERROR"] = counts.get("ERROR", 0) + 1
                continue
            if status == "RATE_LIMITED":
                # Provider quota/rate limit is not a property failure: abort
                # the whole run and leave every remaining row untouched
                # (2026-08-30 incident: exhausted Tavily plan mass-failed 164).
                counts["RATE_LIMITED"] = 1
                log.error("company_refresh_rate_limited_abort", done=index - 1, total=len(ids))
                write_status(
                    status_file,
                    state="failed",
                    mode=mode,
                    total=len(ids),
                    done=index - 1,
                    counts=counts,
                    error=(
                        "Tavily usage limit reached — check aborted, existing "
                        "data untouched. Wait for the quota to reset or "
                        "upgrade the Tavily plan."
                    ),
                )
                return counts
            counts[status] = counts.get(status, 0) + 1
            # Commute analysis rides along with every check (owner request
            # 2026-08-30); a research failure never fails the check itself.
            if status == "CHECKED":
                try:
                    researched = _research_company_commutes(
                        session,
                        llm,
                        prop,
                        settings.providers.commute_research_cache_days,
                    )
                    session.commit()
                    if researched:
                        counts["COMMUTES"] = counts.get("COMMUTES", 0) + researched
                except Exception as exc:  # noqa: BLE001 - batch keeps going
                    session.rollback()
                    log.error(
                        "company_commute_error", property=str(property_id), error=str(exc)
                    )
            log.info(
                "company_refresh_progress",
                index=index,
                total=len(ids),
                name=prop.name,
                status=status,
            )
    log.info("company_refresh_done", counts=counts)
    write_status(
        status_file,
        state="done",
        mode=mode,
        total=len(ids),
        done=len(ids),
        counts=counts,
        finished_at=datetime.now(tz=UTC).isoformat(),
    )
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Company portfolio availability check")
    parser.add_argument(
        "--force", action="store_true", help="recheck even recently checked properties"
    )
    parser.add_argument(
        "--failed-only",
        action="store_true",
        help="only properties whose last check failed (or never ran)",
    )
    parser.add_argument(
        "--commutes-only",
        action="store_true",
        help="skip page checks; research commutes for unit-bearing properties "
        "(needs only the LLM key, not Tavily)",
    )
    args = parser.parse_args()
    configure_logging()
    counts = run_company_refresh(
        force=args.force, failed_only=args.failed_only, commutes_only=args.commutes_only
    )
    return 1 if "MISSING_KEYS" in counts else 0


if __name__ == "__main__":
    sys.exit(main())
