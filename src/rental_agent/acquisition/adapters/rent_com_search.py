"""Rent.com search-index discovery adapter (owner decision 2026-08-18).

Third source. Chosen because — unlike apartments.com — its property pages are
reachable by Tavily Extract (probed live: ~12k chars with laundry, prices, and
floor-plan content), so NJ listings get the same deep enrichment as NYC.
Acquisition posture identical to the other adapters (03 §5.4): bounded
``site:rent.com`` queries, snippet = capture, no scraping, no contact data,
search absence never means disappearance.

Geography partitions follow the owner's 2026-08-18 adjustment: Jersey City is
split into sub-areas (Downtown, Journal Square, Newport, The Heights) instead
of one broad query, plus Hoboken and Fort Lee.
"""

import hashlib
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse, urlunparse

from rental_agent.acquisition.adapters.streeteasy_search import parse_snippet
from rental_agent.contracts import enums as e
from rental_agent.contracts.observation import (
    ExtractionBlock,
    ParsedSourceObservation,
    ValidationBlock,
)
from rental_agent.contracts.providers import (
    AcquisitionPartition,
    DiscoveredItem,
    DiscoveryPage,
    RawListingCapture,
    SearchProvider,
    SearchQuery,
    SearchResultItem,
    SourcePreflightResult,
)

SOURCE_CODE = "rent_com"
ADAPTER_VERSION = "0.1.0"

# 6 geographies x 3 layouts = 18 queries/run.
GEOGRAPHY_TERMS = {
    "nj_jc_downtown": '"Downtown Jersey City"',
    "nj_jc_journal_square": '"Journal Square" "Jersey City"',
    "nj_jc_newport": '"Newport" "Jersey City"',
    "nj_jc_heights": '"The Heights" "Jersey City"',
    "nj_hoboken": '"Hoboken"',
    "nj_fort_lee": '"Fort Lee"',
}
LAYOUT_TERMS = {
    "studio": ("studio", e.LayoutClass.STUDIO),
    "1br": ('"1 bedroom"', e.LayoutClass.ONE_BEDROOM),
    "2br": ('"2 bedroom"', e.LayoutClass.TWO_BEDROOM),
}
_GEO_LABELS = {
    "nj_jc_downtown": "Jersey City",
    "nj_jc_journal_square": "Jersey City",
    "nj_jc_newport": "Jersey City",
    "nj_jc_heights": "Jersey City",
    "nj_hoboken": "Hoboken",
    "nj_fort_lee": "Fort Lee",
}

# Property pages: /apartment/<slug>-lc<digits>; category pages live under
# /new-jersey/... and never match.
_LISTING_PATH_RE = re.compile(r"^/apartment/([\w-]+-lc\d{4,10})$")


def canonicalize_url(url: str) -> str | None:
    """Normalize a rent.com property URL; None for category/trend pages."""
    parsed = urlparse(url)
    if parsed.netloc.removeprefix("www.") != "rent.com":
        return None
    path = parsed.path.rstrip("/")
    if not _LISTING_PATH_RE.match(path):
        return None
    return urlunparse(("https", "www.rent.com", path, "", "", ""))


def native_id_from_url(canonical_url: str) -> str:
    return urlparse(canonical_url).path.strip("/")


class RentComSearchAdapter:
    """SourceAdapter implementation over a SearchProvider (extract-friendly NJ)."""

    interface_version = "1.0.0"
    source_code = SOURCE_CODE
    adapter_version = ADAPTER_VERSION

    def __init__(self, search_provider: SearchProvider, max_results_per_query: int = 20) -> None:
        self._search = search_provider
        self._max_results = max_results_per_query
        self._item_context: dict[str, SearchResultItem] = {}
        self._item_geo: dict[str, str] = {}

    def preflight(self, context: dict[str, Any]) -> SourcePreflightResult:
        if getattr(self._search, "provider_code", "unconfigured") == "unconfigured":
            return SourcePreflightResult(result="BLOCKED", reasons=["search provider unconfigured"])
        return SourcePreflightResult(result="READY")

    def plan_partitions(self, context: dict[str, Any]) -> list[AcquisitionPartition]:
        partitions = []
        for geo_key, geo_term in GEOGRAPHY_TERMS.items():
            for layout_key, (layout_term, _) in LAYOUT_TERMS.items():
                query = f"site:rent.com {layout_term} {geo_term} NJ apartment"
                partitions.append(
                    AcquisitionPartition(
                        source_code=SOURCE_CODE,
                        partition_key=f"{geo_key}:{layout_key}",
                        geography=geo_key,
                        layout=layout_key,
                        query_parameters={"query": query},
                    )
                )
        return partitions

    def discover(
        self, partition: AcquisitionPartition, cursor: dict[str, Any] | None
    ) -> DiscoveryPage:
        response = self._search.search(
            SearchQuery(query=partition.query_parameters["query"], max_results=self._max_results)
        )
        if response.status is not e.ProviderRequestStatus.SUCCEEDED:
            return DiscoveryPage(
                items=[],
                appears_truncated=True,
                health_markers={"search_error": response.error_code},
            )
        items: list[DiscoveredItem] = []
        seen: set[str] = set()
        for result in response.items:
            canonical = canonicalize_url(result.url)
            if canonical is None or canonical in seen:
                continue
            seen.add(canonical)
            self._item_context[canonical] = result
            geo_label = _GEO_LABELS.get(partition.geography)
            if geo_label:
                self._item_geo[canonical] = geo_label
            items.append(
                DiscoveredItem(
                    source_native_id=native_id_from_url(canonical),
                    detail_url=canonical,
                    card_facts={"title": result.title, "snippet": result.snippet},
                )
            )
        return DiscoveryPage(
            items=items,
            appears_truncated=len(response.items) >= self._max_results,
            health_markers={"result_count": len(response.items)},
        )

    def fetch_detail(self, item: DiscoveredItem) -> RawListingCapture:
        # Search-index discovery has no detail fetch: the snippet IS the capture.
        result = self._item_context.get(item.detail_url) or SearchResultItem(url=item.detail_url)
        payload = f"{result.title or ''}|{result.snippet or ''}"
        return RawListingCapture(
            final_url=item.detail_url,
            retrieved_at=datetime.now(tz=UTC),
            content_hash=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
            structured_blocks={
                "title": result.title,
                "snippet": result.snippet,
                "geo_label": self._item_geo.get(item.detail_url),
            },
            structural_signature="search_snippet_v1",
        )

    def extract(self, capture: RawListingCapture) -> ParsedSourceObservation:
        title = capture.structured_blocks.get("title")
        snippet = capture.structured_blocks.get("snippet")
        pricing, layout, identity, description = parse_snippet(title, snippet)
        geo_label = capture.structured_blocks.get("geo_label")
        if geo_label:
            identity.source_geographic_labels = [geo_label]
        now = datetime.now(tz=UTC)
        return ParsedSourceObservation(
            source_code=SOURCE_CODE,
            source_native_id=native_id_from_url(capture.final_url),
            source_url=capture.final_url,
            observed_at=capture.retrieved_at,
            retrieved_at=now,
            source_status="UNKNOWN",  # a snippet cannot prove current availability
            identity=identity,
            pricing=pricing,
            layout=layout,
            description=description,
            extraction=ExtractionBlock(
                adapter_version=ADAPTER_VERSION,
                extraction_paths=["search_snippet"],
                confidence=e.Confidence.LOW,
                fields_requiring_review=["availability", "address"],
            ),
            validation=ValidationBlock(parse_status=e.ParseStatus.PARTIAL),
        )
