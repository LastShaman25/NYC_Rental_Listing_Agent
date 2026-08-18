"""Apartments.com adapter: URL canonicalization, partitions, snippet extraction."""

from rental_agent.acquisition.adapters.apartments_com_search import (
    ApartmentsComSearchAdapter,
    canonicalize_url,
    native_id_from_url,
)
from rental_agent.contracts import enums as e
from rental_agent.contracts.providers import (
    AcquisitionPartition,
    SearchQuery,
    SearchResponse,
    SearchResultItem,
)


def test_canonicalize_accepts_property_pages() -> None:
    url = "https://www.apartments.com/the-modern-fort-lee-nj/abc1234/?utm=x"
    assert canonicalize_url(url) == "https://www.apartments.com/the-modern-fort-lee-nj/abc1234/"
    assert native_id_from_url(canonicalize_url(url)) == "the-modern-fort-lee-nj/abc1234"
    # Letter-only property codes are real (seen live: 601-jackson-st .../pxmgrqs).
    assert (
        canonicalize_url("https://www.apartments.com/601-jackson-st-hoboken-nj/pxmgrqs/")
        is not None
    )


def test_canonicalize_rejects_category_and_trend_pages() -> None:
    for url in (
        "https://www.apartments.com/fort-lee-nj/3-bedrooms/",
        "https://www.apartments.com/fort-lee-nj/",
        "https://www.apartments.com/rent-market-trends/fort-lee-nj/",
        "https://www.apartments.com/fort-lee-nj/short-term/",
        "https://www.apartments.com/fort-lee-nj/luxury/",  # word-only segment
        "https://www.apartments.com/fort-lee-nj/balcony/",
        "https://www.renthop.com/the-modern-fort-lee-nj/abc1234/",
    ):
        assert canonicalize_url(url) is None, url


class _FakeSearch:
    provider_code = "fake"

    def __init__(self, items: list[SearchResultItem]) -> None:
        self._items = items

    def search(self, request: SearchQuery) -> SearchResponse:
        return SearchResponse(status=e.ProviderRequestStatus.SUCCEEDED, items=self._items)


def test_partitions_cover_fort_lee_only() -> None:
    # Trimmed 2026-08-18: rent.com owns JC/Hoboken (extract-friendly);
    # apartments.com keeps its unique Fort Lee depth.
    adapter = ApartmentsComSearchAdapter(_FakeSearch([]))
    partitions = adapter.plan_partitions({})
    keys = {p.partition_key for p in partitions}
    assert len(partitions) == 3
    assert keys == {"nj_fort_lee:studio", "nj_fort_lee:1br", "nj_fort_lee:2br"}
    assert all(p.source_code == "apartments_com" for p in partitions)


def test_discover_and_extract_carries_geo_label() -> None:
    items = [
        SearchResultItem(
            url="https://www.apartments.com/hudson-lights-fort-lee-nj/x9y8z7w/",
            title="Hudson Lights - 30 Park Ave, Fort Lee, NJ",
            snippet="1 bedroom apartments from $2,850 per month. In-unit washer/dryer.",
        ),
        SearchResultItem(url="https://www.apartments.com/fort-lee-nj/3-bedrooms/"),
    ]
    adapter = ApartmentsComSearchAdapter(_FakeSearch(items))
    partition = AcquisitionPartition(
        source_code="apartments_com",
        partition_key="nj_fort_lee:1br",
        geography="nj_fort_lee",
        layout="1br",
        query_parameters={"query": "q"},
    )
    page = adapter.discover(partition, None)
    assert len(page.items) == 1  # category page filtered out
    capture = adapter.fetch_detail(page.items[0])
    observation = adapter.extract(capture)
    assert observation.source_code == "apartments_com"
    assert observation.identity.source_geographic_labels == ["Fort Lee"]
    assert observation.pricing.monthly_rent_minor == 285_000
    assert observation.layout.proposed_layout_class is e.LayoutClass.ONE_BEDROOM
    assert observation.identity.raw_address_text is not None
