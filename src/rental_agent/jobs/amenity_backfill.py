"""Amenity backfill across ALL properties (owner request 2026-08-30).

Run: uv run --no-sync python -m rental_agent.jobs.amenity_backfill

Fills amenity gaps via hosted web research (OpenAI web-search — works even
while the Tavily plan is exhausted):

- company properties whose availability snapshot has no amenities;
- acquired listings without a current ``amenities`` fact resolution.

Sources are required (04 §19A posture); page-extracted facts stay preferred
and simply supersede these on the next successful page check. Commits per
property; a failure never rolls back earlier work.
"""

import sys

from sqlalchemy import text as sql_text

from rental_agent.config.logging import configure_logging, get_logger
from rental_agent.config.settings import load_settings
from rental_agent.db.engine import build_engine, build_session_factory
from rental_agent.db.models import CompanyProperty
from rental_agent.enrichment.amenities.research import AmenityResearchService
from rental_agent.enrichment.llm.openai_executor import executor_from_settings
from rental_agent.jobs.company_refresh import write_status

log = get_logger(__name__)

STATUS_FILENAME = "amenity_backfill_status.json"


def run_amenity_backfill() -> dict[str, int]:
    settings = load_settings()
    status_file = settings.paths.logs / STATUS_FILENAME
    try:
        llm = executor_from_settings(settings.providers)
    except ValueError:
        log.error("amenity_backfill_missing_llm_key")
        write_status(status_file, state="failed", error="LLM API key missing")
        return {"MISSING_KEYS": 1}
    factory = build_session_factory(build_engine(settings))

    with factory() as session:
        company_ids = list(
            session.execute(
                sql_text(
                    "SELECT company_property_id FROM app.company_property "
                    "WHERE check_status = 'CHECKED' AND availability IS NOT NULL "
                    "  AND jsonb_array_length("
                    "      COALESCE(availability->'amenities', '[]'::jsonb)) = 0 "
                    "ORDER BY name"
                )
            ).scalars()
        )
        listing_rows = session.execute(
            sql_text(
                "SELECT cl.canonical_listing_id, a.formatted_address, a.locality "
                "FROM app.canonical_listing cl "
                "JOIN app.building b ON b.building_id = cl.building_id "
                "JOIN app.address a ON a.address_id = b.address_id "
                "WHERE cl.lifecycle_status IN ('ACTIVE', 'CANDIDATE', 'REAPPEARED') "
                "AND NOT EXISTS ("
                "  SELECT 1 FROM app.fact_resolution fr "
                "  WHERE fr.entity_id = cl.canonical_listing_id "
                "    AND fr.fact_key = 'amenities' AND fr.superseded_at IS NULL)"
            )
        ).all()
    total = len(company_ids) + len(listing_rows)
    log.info(
        "amenity_backfill_start", company=len(company_ids), listings=len(listing_rows)
    )
    counts: dict[str, int] = {}
    done = 0
    write_status(status_file, state="running", total=total, done=0, counts=counts)

    for property_id in company_ids:
        done += 1
        with factory() as session:
            prop = session.get(CompanyProperty, property_id)
            if prop is None:
                continue
            service = AmenityResearchService(session, llm)
            try:
                output = service.research(
                    name=prop.name,
                    address=", ".join(
                        p for p in (prop.address_text, prop.locality) if p
                    )
                    or "New York",
                    hint_url=prop.resolved_url or prop.original_url,
                )
                if output is not None:
                    service.apply_to_company(prop, output)
                    session.commit()
                    counts["COMPANY_FILLED"] = counts.get("COMPANY_FILLED", 0) + 1
                else:
                    counts["NO_DATA"] = counts.get("NO_DATA", 0) + 1
            except Exception as exc:  # noqa: BLE001 - batch keeps going
                session.rollback()
                log.error("amenity_backfill_error", target=str(property_id), error=str(exc))
                counts["ERROR"] = counts.get("ERROR", 0) + 1
        write_status(
            status_file, state="running", total=total, done=done, counts=counts,
            current=str(property_id),
        )

    for listing_id, formatted_address, locality in listing_rows:
        done += 1
        with factory() as session:
            service = AmenityResearchService(session, llm)
            try:
                output = service.research(
                    name=formatted_address,
                    address=f"{formatted_address}, {locality or 'New York'}",
                )
                if output is not None:
                    service.record_listing_fact(listing_id, output)
                    session.commit()
                    counts["LISTING_FILLED"] = counts.get("LISTING_FILLED", 0) + 1
                else:
                    counts["NO_DATA"] = counts.get("NO_DATA", 0) + 1
            except Exception as exc:  # noqa: BLE001 - batch keeps going
                session.rollback()
                log.error("amenity_backfill_error", target=str(listing_id), error=str(exc))
                counts["ERROR"] = counts.get("ERROR", 0) + 1
        write_status(
            status_file, state="running", total=total, done=done, counts=counts
        )

    log.info("amenity_backfill_done", counts=counts)
    write_status(status_file, state="done", total=total, done=done, counts=counts)
    return counts


def main() -> int:
    configure_logging()
    counts = run_amenity_backfill()
    return 1 if "MISSING_KEYS" in counts else 0


if __name__ == "__main__":
    sys.exit(main())
