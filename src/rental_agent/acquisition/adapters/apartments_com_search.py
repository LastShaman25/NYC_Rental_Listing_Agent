"""Apartments.com search-index discovery adapter (owner decision 2026-08-18).

Second source, covering the NJ areas StreetEasy lacks: Jersey City, Hoboken,
Fort Lee. Same acquisition posture as StreetEasy (03 §5.4): bounded
``site:apartments.com`` queries on the configured SearchProvider — never
scraping the site directly; snippets yield PARTIAL observations; absence from
search results is never disappearance evidence; no contact data extracted.

Apartments.com is complex-heavy: a discovered property page usually represents
a building with several units. The snippet's first plausible price seeds the
rent (like StreetEasy), and the detail-page enrichment pass later corrects it
against the actual page (same machinery that fixed the snippet-rent bug).
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

SOURCE_CODE = "apartments_com"
ADAPTER_VERSION = "0.1.0"

# Bounded query partitions. Trimmed to Fort Lee only (owner 2026-08-18):
# apartments.com is this pipeline's only real Fort Lee source, but its pages
# block Tavily Extract, so rent.com (extract-friendly) owns Jersey City and
# Hoboken with sub-area partitions. Also keeps the monthly Tavily quota inside
# the free tier. 1 geography x 3 layouts = 3 queries/run.
GEOGRAPHY_TERMS = {
    "nj_fort_lee": '"Fort Lee"',
}
LAYOUT_TERMS = {
    "studio": ("studio", e.LayoutClass.STUDIO),
    "1br": ('"1 bedroom"', e.LayoutClass.ONE_BEDROOM),
    "2br": ('"2 bedroom"', e.LayoutClass.TWO_BEDROOM),
}
_GEO_LABELS = {
    "nj_fort_lee": "Fort Lee",
}

# Property pages: /<name-or-address>-<city>-nj/<compact-code>/. Category pages
# use the BARE city slug (/hoboken-nj/luxury, /fort-lee-nj/3-bedrooms) while
# real properties always prefix it (/601-jackson-st-hoboken-nj/pxmgrqs) — the
# code segment can be letter-only, so the slug is the discriminator
# (calibrated on the 2026-08-18 first live run, which leaked 8 category rows).
_LISTING_PATH_RE = re.compile(r"^/([\w-]+-nj)/([a-z0-9]{5,10})$")
_CITY_SLUGS = frozenset({"jersey-city-nj", "hoboken-nj", "fort-lee-nj"})


def canonicalize_url(url: str) -> str | None:
    """Normalize an apartments.com property URL; None for category/trend pages."""
    parsed = urlparse(url)
    if parsed.netloc.removeprefix("www.") != "apartments.com":
        return None
    path = parsed.path.rstrip("/")
    match = _LISTING_PATH_RE.match(path)
    if match is None or match.group(1) in _CITY_SLUGS:
        return None
    return urlunparse(("https", "www.apartments.com", path + "/", "", "", ""))


def native_id_from_url(canonical_url: str) -> str:
    return urlparse(canonical_url).path.strip("/")


class ApartmentsComSearchAdapter:
    """SourceAdapter implementation over a SearchProvider (NJ coverage)."""

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
                query = f"site:apartments.com {layout_term} {geo_term} NJ apartment for rent"
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
        # Deterministic snippet parsing is source-agnostic; reuse StreetEasy's.
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
