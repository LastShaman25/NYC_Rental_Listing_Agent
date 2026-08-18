"""Rent.com adapter: URL canonicalization, partitions, snippet extraction."""

from rental_agent.acquisition.adapters.rent_com_search import (
    RentComSearchAdapter,
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
    url = "https://www.rent.com/apartment/the-journal-jersey-city-nj-lc6215737?utm=x"
    canonical = canonicalize_url(url)
    assert canonical == "https://www.rent.com/apartment/the-journal-jersey-city-nj-lc6215737"
    assert native_id_from_url(canonical) == "apartment/the-journal-jersey-city-nj-lc6215737"


def test_canonicalize_rejects_category_pages() -> None:
    for url in (
        "https://www.rent.com/new-jersey/jersey-city-apartments/",
        "https://www.rent.com/new-jersey/jersey-city-apartments/rent-trends/",
        "https://www.rent.com/new-jersey/jersey-city-apartments/exchange-place-north-neighborhood",
        "https://www.rent.com/apartment/not-a-listing",  # no -lc<digits> suffix
        "https://www.apartments.com/apartment/the-journal-jersey-city-nj-lc6215737",
    ):
        assert canonicalize_url(url) is None, url


class _FakeSearch:
    provider_code = "fake"

    def __init__(self, items: list[SearchResultItem]) -> None:
        self._items = items

    def search(self, request: SearchQuery) -> SearchResponse:
        return SearchResponse(status=e.ProviderRequestStatus.SUCCEEDED, items=self._items)


def test_partitions_split_jersey_city() -> None:
    adapter = RentComSearchAdapter(_FakeSearch([]))
    partitions = adapter.plan_partitions({})
    assert len(partitions) == 18  # 6 geographies x 3 layouts
    keys = {p.partition_key for p in partitions}
    assert "nj_jc_journal_square:studio" in keys
    assert "nj_jc_downtown:2br" in keys
    assert "nj_fort_lee:1br" in keys


def test_discover_and_extract() -> None:
    items = [
        SearchResultItem(
            url="https://www.rent.com/apartment/portside-towers-jersey-city-nj-lc123456",
            title="Portside Towers - 155 Washington St, Jersey City, NJ",
            snippet="Studio from $2,700 per month. Building laundry.",
        ),
        SearchResultItem(url="https://www.rent.com/new-jersey/jersey-city-apartments/"),
    ]
    adapter = RentComSearchAdapter(_FakeSearch(items))
    partition = AcquisitionPartition(
        source_code="rent_com",
        partition_key="nj_jc_downtown:studio",
        geography="nj_jc_downtown",
        layout="studio",
        query_parameters={"query": "q"},
    )
    page = adapter.discover(partition, None)
    assert len(page.items) == 1
    observation = adapter.extract(adapter.fetch_detail(page.items[0]))
    assert observation.source_code == "rent_com"
    assert observation.identity.source_geographic_labels == ["Jersey City"]
    assert observation.pricing.monthly_rent_minor == 270_000
    assert observation.layout.proposed_layout_class is e.LayoutClass.STUDIO
