"""Tavily SearchProvider wire tests (no live calls)."""

import urllib.error

import pytest

from rental_agent.acquisition.search_tavily import TavilySearchProvider, split_site_restriction
from rental_agent.contracts import enums as e
from rental_agent.contracts.providers import SearchQuery


def test_requires_api_key():
    with pytest.raises(ValueError):
        TavilySearchProvider("")


def test_site_token_becomes_domain_restriction():
    clean, domains = split_site_restriction('site:streeteasy.com "1 bed" "Manhattan" rental')
    assert domains == ["streeteasy.com"]
    assert clean == '"1 bed" "Manhattan" rental'


def test_search_maps_results_and_restricts_domain():
    calls: list[tuple[str, dict, str]] = []

    def poster(url, body, key):
        calls.append((url, body, key))
        return {
            "results": [
                {
                    "url": "https://streeteasy.com/rental/123",
                    "title": "1 bed at 5 Main St",
                    "content": "$3,400/month one bedroom.",
                    "score": 0.9,
                }
            ]
        }

    provider = TavilySearchProvider("tvly-test", poster=poster)
    response = provider.search(
        SearchQuery(query="site:streeteasy.com studio Manhattan rental", max_results=10)
    )
    assert response.status is e.ProviderRequestStatus.SUCCEEDED
    assert response.items[0].url == "https://streeteasy.com/rental/123"
    assert response.items[0].snippet == "$3,400/month one bedroom."
    assert response.items[0].rank == 1
    _, body, key = calls[0]
    assert body["include_domains"] == ["streeteasy.com"]
    assert "site:" not in body["query"]
    assert body["max_results"] == 10
    assert key == "tvly-test"


def test_max_results_capped_at_tavily_limit():
    def poster(url, body, key):
        assert body["max_results"] == 20
        return {"results": []}

    TavilySearchProvider("tvly-test", poster=poster).search(SearchQuery(query="q", max_results=100))


def test_rate_limit_maps_to_typed_status():
    def poster(url, body, key):
        raise urllib.error.HTTPError(url, 429, "rate limited", hdrs=None, fp=None)

    response = TavilySearchProvider("tvly-test", poster=poster).search(SearchQuery(query="q"))
    assert response.status is e.ProviderRequestStatus.RATE_LIMITED
    assert response.error_code == "HTTP_429"


def test_transport_error_is_typed_failure():
    def poster(url, body, key):
        raise TimeoutError("slow")

    response = TavilySearchProvider("tvly-test", poster=poster).search(SearchQuery(query="q"))
    assert response.status is e.ProviderRequestStatus.FAILED
    assert response.error_code == "TRANSPORT_TimeoutError"
