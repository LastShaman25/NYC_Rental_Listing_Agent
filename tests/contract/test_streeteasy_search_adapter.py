"""StreetEasy search-index discovery adapter contract tests (03 §5.4)."""

from rental_agent.acquisition.adapters.streeteasy_search import (
    StreetEasySearchAdapter,
    canonicalize_url,
    parse_snippet,
)
from rental_agent.contracts import enums as e
from rental_agent.contracts.fakes import FakeSearchProvider
from rental_agent.contracts.providers import SearchResponse, SearchResultItem


def _adapter_with(items: list[SearchResultItem]) -> StreetEasySearchAdapter:
    provider = FakeSearchProvider()
    provider.responses = {}
    adapter = StreetEasySearchAdapter(provider)
    for partition in adapter.plan_partitions({}):
        provider.responses[partition.query_parameters["query"]] = SearchResponse(
            status=e.ProviderRequestStatus.SUCCEEDED, items=items
        )
    return adapter


def test_partitions_are_bounded_geography_by_layout():
    adapter = StreetEasySearchAdapter(FakeSearchProvider())
    partitions = adapter.plan_partitions({})
    assert len(partitions) == 9 * 3  # (boroughs + neighborhoods incl. Inwood) x layouts
    for p in partitions:
        assert p.query_parameters["query"].startswith("site:streeteasy.com ")


def test_url_canonicalization():
    assert (
        canonicalize_url("https://www.streeteasy.com/building/the-foo/12b?featured=1&src=x")
        == "https://streeteasy.com/building/the-foo/12b"
    )
    assert canonicalize_url("https://streeteasy.com/rental/4567890") is not None
    assert canonicalize_url("https://streeteasy.com/blog/some-article") is None
    assert canonicalize_url("https://evil.example/building/the-foo/12b") is None


def test_snippet_parsing_extracts_price_layout_address():
    pricing, layout, identity, description = parse_snippet(
        "225 East 34th Street #12B - 1 bed for rent",
        "This 1 bedroom apartment rents for $4,250/month. In-unit washer and dryer.",
    )
    assert pricing.monthly_rent_minor == 425000
    assert layout.proposed_layout_class is e.LayoutClass.ONE_BEDROOM
    assert identity.raw_address_text is not None
    assert "225" in identity.raw_address_text
    assert identity.raw_unit_label == "12B"


def test_snippet_contact_data_is_redacted():
    _, _, _, description = parse_snippet(
        "123 Main Street - Studio",
        "Call (212) 555-0134 or email agent@broker.example to schedule a viewing.",
    )
    assert "(212) 555-0134" not in (description.text or "")
    assert "agent@broker.example" not in (description.text or "")
    assert description.redaction_status is e.ContactRedactionStatus.REDACTED


def test_three_plus_bedrooms_marked_out_of_scope():
    _, layout, _, _ = parse_snippet("789 Park Avenue", "Spacious 3 bedroom home, $9,000/mo")
    assert layout.proposed_layout_class is e.LayoutClass.OUT_OF_SCOPE


def test_end_to_end_discovery_to_partial_observation():
    items = [
        SearchResultItem(
            url="https://www.streeteasy.com/building/foo-tower/4a?src=serp",
            title="Foo Tower #4A - 2 bed at 100 Water Street",
            snippet="2 bedroom, 2 bath at $5,995/month in Financial District.",
            rank=1,
        ),
        # duplicate under different tracking params must dedupe
        SearchResultItem(
            url="https://streeteasy.com/building/foo-tower/4a",
            title="Foo Tower #4A",
            snippet=None,
            rank=2,
        ),
        SearchResultItem(url="https://streeteasy.com/blog/market-report", title="Blog", rank=3),
    ]
    adapter = _adapter_with(items)
    [partition, *_] = adapter.plan_partitions({})
    page = adapter.discover(partition, None)
    assert len(page.items) == 1  # dedup + non-listing URL dropped
    capture = adapter.fetch_detail(page.items[0])
    observation = adapter.extract(capture)
    assert observation.source_code == "streeteasy"
    assert observation.validation.parse_status is e.ParseStatus.PARTIAL
    assert observation.pricing.monthly_rent_minor == 599500
    assert observation.layout.proposed_layout_class is e.LayoutClass.TWO_BEDROOM
    assert observation.source_status == "UNKNOWN"  # snippet cannot prove availability
    assert "search_snippet" in observation.extraction.extraction_paths


def test_failed_search_degrades_instead_of_zero_listings():
    adapter = StreetEasySearchAdapter(FakeSearchProvider())  # no responses configured
    [partition, *_] = adapter.plan_partitions({})
    page = adapter.discover(partition, None)
    assert page.items == []
    assert page.appears_truncated is True  # forces DEGRADED handling, not "empty market"
    assert "search_error" in page.health_markers
