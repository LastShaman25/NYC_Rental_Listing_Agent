"""StreetEasy search-index discovery adapter (03 §5.4, owner decision B3).

Discovers StreetEasy listings through bounded ``site:streeteasy.com`` queries on
a configurable SearchProvider — never by scraping StreetEasy directly. Snippet
data yields PARTIAL observations whose source links are marked SEARCH_INDEX;
absence from search results is never disappearance evidence, and the adapter
extracts no broker/contact information.
"""

import hashlib
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse, urlunparse

from rental_agent.contracts import enums as e
from rental_agent.contracts.observation import (
    DescriptionBlock,
    ExtractionBlock,
    IdentityBlock,
    LayoutBlock,
    ParsedSourceObservation,
    PricingBlock,
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

SOURCE_CODE = "streeteasy"
ADAPTER_VERSION = "0.1.0"

# Bounded query partitions: geography x layout (03 §11.1–11.2).
# Calibrated 2026-08-17 against live Tavily results: borough partitions provide
# breadth; the added neighborhood partitions raise individual-listing yield
# (borough-only queries mostly surface landing pages). Quota math: 8 geographies
# x 3 layouts = 24 queries/run, ~530/month at weekday cadence vs 1,000 free.
GEOGRAPHY_TERMS = {
    "nyc_manhattan": '"Manhattan"',
    "nyc_brooklyn": '"Brooklyn"',
    "nyc_queens": '"Queens"',
    "nyc_bronx": '"Bronx"',
    "nbhd_upper_east_side": '"Upper East Side"',
    "nbhd_astoria": '"Astoria"',
    "nbhd_bushwick": '"Bushwick"',
    "nbhd_harlem": '"Harlem"',
    # Owner request 2026-08-29: Inwood coverage was missing from the map.
    "nbhd_inwood": '"Inwood"',
    # StreetEasy is NYC-focused; NJ coverage comes from other sources.
}
LAYOUT_TERMS = {
    "studio": ("studio", e.LayoutClass.STUDIO),
    "1br": ('"1 bed"', e.LayoutClass.ONE_BEDROOM),
    "2br": ('"2 bed"', e.LayoutClass.TWO_BEDROOM),
}

_PRICE_RE = re.compile(r"\$\s?([\d,]{3,10})(?:\s*(?:/|per\s*)mo(?:nth)?)?", re.IGNORECASE)
_LAYOUT_PATTERNS: list[tuple[re.Pattern[str], e.LayoutClass]] = [
    (re.compile(r"\bstudio\b", re.I), e.LayoutClass.STUDIO),
    (re.compile(r"\b(?:1|one)[\s-]*(?:bed(?:room)?|br)\b", re.I), e.LayoutClass.ONE_BEDROOM),
    (re.compile(r"\b(?:2|two)[\s-]*(?:bed(?:room)?|br)\b", re.I), e.LayoutClass.TWO_BEDROOM),
    (
        re.compile(r"\b(?:[3-9]|three|four|five)[\s-]*(?:bed(?:room)?|br)\b", re.I),
        e.LayoutClass.OUT_OF_SCOPE,
    ),
]
# StreetEasy listing URLs look like /building/<building-slug>/<unit> or /rental/<id>
_LISTING_PATH_RE = re.compile(r"^/(building/[^/]+/[^/]+|rental/\d+)/?$")
# Leading "123 Main Street #4B - ..." or "123 Main St, New York" title shapes.
_ADDRESS_RE = re.compile(
    r"(\d{1,5}[\w\-]*\s+(?:[A-Z0-9][\w'.]*\s?){1,5}"
    r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Place|Pl|Drive|Dr|Lane|Ln|Court|Ct|"
    r"Terrace|Ter|Parkway|Pkwy|Broadway|Way)\b\.?(?:\s*(?:East|West|North|South))?)",
)
_UNIT_RE = re.compile(r"#\s?([\w-]{1,8})")
# Contact-looking fragments are dropped from retained snippet text (PR-ACQ-005).
_CONTACT_RE = re.compile(
    r"(\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4})|([\w.+-]+@[\w-]+\.[\w.]+)", re.IGNORECASE
)


def canonicalize_url(url: str) -> str | None:
    """Normalize a StreetEasy listing URL; returns None for non-listing URLs."""
    parsed = urlparse(url)
    if parsed.netloc.removeprefix("www.") != "streeteasy.com":
        return None
    path = parsed.path.rstrip("/")
    if not _LISTING_PATH_RE.match(path + "/") and not _LISTING_PATH_RE.match(path):
        return None
    # Tracking params are dropped; StreetEasy listing identity lives in the path.
    return urlunparse(("https", "streeteasy.com", path, "", "", ""))


def native_id_from_url(canonical_url: str) -> str:
    return urlparse(canonical_url).path.strip("/")


def parse_snippet(
    title: str | None, snippet: str | None
) -> tuple[PricingBlock, LayoutBlock, IdentityBlock, DescriptionBlock]:
    """Deterministic extraction from search title/snippet only."""
    text = " ".join(part for part in (title, snippet) if part)
    redacted = _CONTACT_RE.sub("[redacted]", text)
    had_contact = redacted != text

    price_match = _PRICE_RE.search(redacted)
    rent_minor: int | None = None
    if price_match:
        dollars = int(price_match.group(1).replace(",", ""))
        # Sanity band: search snippets sometimes show sale prices; keep only
        # plausible monthly rents (parser-unit guard, 03 §19.2).
        if 500 <= dollars <= 100_000:
            rent_minor = dollars * 100

    layout = e.LayoutClass.UNKNOWN
    for pattern, cls in _LAYOUT_PATTERNS:
        if pattern.search(redacted):
            layout = cls
            break

    address_match = _ADDRESS_RE.search(redacted)
    unit_match = _UNIT_RE.search(redacted)

    pricing = PricingBlock(
        source_price_text=price_match.group(0) if price_match else None,
        monthly_rent_minor=rent_minor,
        price_type="EXACT_MONTHLY_ASKING" if rent_minor is not None else "UNKNOWN",
        evidence=[{"kind": "search_snippet", "text": price_match.group(0)}] if price_match else [],
    )
    layout_block = LayoutBlock(
        raw_layout_text=redacted[:200] if layout is not e.LayoutClass.UNKNOWN else None,
        proposed_layout_class=layout,
        confidence=e.Confidence.MEDIUM
        if layout is not e.LayoutClass.UNKNOWN
        else e.Confidence.UNKNOWN,
    )
    identity = IdentityBlock(
        raw_address_text=address_match.group(1) if address_match else None,
        raw_unit_label=unit_match.group(1) if unit_match else None,
    )
    description = DescriptionBlock(
        text=redacted or None,
        redaction_status=(
            e.ContactRedactionStatus.REDACTED
            if had_contact
            else e.ContactRedactionStatus.NOT_PRESENT
        ),
    )
    return pricing, layout_block, identity, description


class StreetEasySearchAdapter:
    """SourceAdapter implementation over a SearchProvider."""

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
                # "building" biases results toward /building/<slug>/<unit> listing
                # pages instead of borough landing pages (calibrated 2026-08-17:
                # 0% -> ~33% listing-URL yield).
                query = f"site:streeteasy.com {layout_term} {geo_term} rental building"
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

    # Human-readable geography per partition key, carried into observations so
    # normalization gets a locality instead of UNRESOLVED.
    _GEO_LABELS = {
        "nyc_manhattan": "Manhattan",
        "nyc_brooklyn": "Brooklyn",
        "nyc_queens": "Queens",
        "nyc_bronx": "Bronx",
        "nbhd_upper_east_side": "Manhattan",
        "nbhd_astoria": "Queens",
        "nbhd_bushwick": "Brooklyn",
        "nbhd_harlem": "Manhattan",
    }

    def discover(
        self, partition: AcquisitionPartition, cursor: dict[str, Any] | None
    ) -> DiscoveryPage:
        response = self._search.search(
            SearchQuery(query=partition.query_parameters["query"], max_results=self._max_results)
        )
        if response.status is not e.ProviderRequestStatus.SUCCEEDED:
            # A failed search query yields an empty, truncated-looking page so the
            # source run degrades; it must never look like "zero listings exist".
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
            geo_label = self._GEO_LABELS.get(partition.geography)
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
