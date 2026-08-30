"""Batch detail-page enrichment for active inventory (owner decision 2026-08-18).

Run: uv run --no-sync python -m rental_agent.jobs.detail_enrichment [--limit N]

For every ACTIVE/CANDIDATE/REAPPEARED listing with an ACTIVE source link,
fetches the listing page via Tavily Extract and fills laundry / floor plan /
amenities / fee facts (see enrichment.listing_content.service). Idempotent:
unchanged pages are skipped, so re-runs cost one extract per listing and zero
LLM calls for unchanged content. Commits per listing — a failure never rolls
back earlier listings.
"""

import argparse
import sys

from sqlalchemy import select

from rental_agent.config.logging import configure_logging, get_logger
from rental_agent.config.settings import load_settings
from rental_agent.db.engine import build_engine, build_session_factory
from rental_agent.db.models import CanonicalListing
from rental_agent.enrichment.listing_content.service import (
    ListingContentEnrichmentService,
    TavilyExtractClient,
)
from rental_agent.enrichment.llm.openai_executor import executor_from_settings

log = get_logger(__name__)

_LIFECYCLES = ("ACTIVE", "CANDIDATE", "REAPPEARED")


def run_detail_enrichment(*, limit: int = 0, force: bool = False) -> dict[str, int]:
    """Enrich active inventory from listing pages; returns status counts."""
    settings = load_settings()
    search_key = settings.providers.search_provider_api_key
    openai_key = settings.providers.openai_api_key
    if search_key is None or openai_key is None:
        log.error("detail_enrichment_missing_keys")
        return {"MISSING_KEYS": 1}
    from rental_agent.acquisition.search_tavily import TavilySearchProvider

    extract_client = TavilyExtractClient(search_key.get_secret_value())
    # Enables the official-building-website fallback for aggregator pages
    # that block extraction (owner decision 2026-08-18).
    search_provider = TavilySearchProvider(search_key.get_secret_value())
    llm = executor_from_settings(settings.providers)
    factory = build_session_factory(build_engine(settings))

    with factory() as session:
        ids = [
            row
            for row in session.execute(
                select(CanonicalListing.canonical_listing_id)
                .where(CanonicalListing.lifecycle_status.in_(_LIFECYCLES))
                .order_by(CanonicalListing.last_seen_at.desc())
            ).scalars()
        ]
    if limit:
        ids = ids[:limit]
    log.info("detail_enrichment_start", listings=len(ids))

    from rental_agent.enrichment.listing_content.service import TavilyQuotaError

    counts: dict[str, int] = {}
    for index, listing_id in enumerate(ids, start=1):
        with factory() as session:
            service = ListingContentEnrichmentService(
                session, llm, extract_client, search_provider=search_provider
            )
            try:
                outcome = service.enrich(listing_id, force=force)
                session.commit()
            except TavilyQuotaError as exc:
                # Account-level limit: abort the batch instead of burning
                # through every listing (2026-08-30 incident).
                session.rollback()
                log.error("detail_enrichment_rate_limited_abort", error=str(exc))
                counts["RATE_LIMITED"] = 1
                break
            except Exception as exc:  # noqa: BLE001 - batch keeps going
                session.rollback()
                log.error("detail_enrichment_error", listing=str(listing_id), error=str(exc))
                counts["ERROR"] = counts.get("ERROR", 0) + 1
                continue
        counts[outcome.status] = counts.get(outcome.status, 0) + 1
        log.info(
            "detail_enrichment_progress",
            index=index,
            total=len(ids),
            listing=str(listing_id),
            status=outcome.status,
            facts=outcome.facts_written,
        )
    log.info("detail_enrichment_done", counts=counts)
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Detail-page enrichment pass")
    parser.add_argument("--limit", type=int, default=0, help="max listings (0 = all)")
    parser.add_argument(
        "--force",
        action="store_true",
        help="re-extract even when the page content is unchanged (bad prior query)",
    )
    args = parser.parse_args()
    configure_logging()
    counts = run_detail_enrichment(limit=args.limit, force=args.force)
    return 1 if "MISSING_KEYS" in counts else 0


if __name__ == "__main__":
    sys.exit(main())
