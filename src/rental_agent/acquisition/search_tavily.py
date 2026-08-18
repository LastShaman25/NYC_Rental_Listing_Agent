"""Tavily SearchProvider (owner decision 2026-08-17, replacing the retired
Google Custom Search JSON API).

Backs StreetEasy search-index discovery (03 §5.4). ``site:domain`` tokens in the
query are translated into Tavily's ``include_domains`` restriction, which is a
hard domain filter. Requires RENTAL_PROVIDER_SEARCH_PROVIDER_API_KEY (a Tavily
key, ``tvly-…``). Free tier ~1,000 credits/month covers the weekday cadence
(~250–400 queries/month).

HTTP transport is injectable so tests never make live calls.
"""

import json
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from rental_agent.config.logging import get_logger
from rental_agent.contracts import enums as e
from rental_agent.contracts.providers import SearchQuery, SearchResponse, SearchResultItem

log = get_logger(__name__)

API_ENDPOINT = "https://api.tavily.com/search"
MAX_RESULTS_PER_REQUEST = 20  # Tavily maximum

_SITE_TOKEN_RE = re.compile(r"site:(\S+)\s*")

Poster = Callable[[str, dict[str, Any], str], dict[str, Any]]
"""(url, json_body, api_key) -> decoded JSON response. Raises on transport error."""


def _default_poster(url: str, body: dict[str, Any], api_key: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - https only
        return json.loads(response.read().decode("utf-8"))


def split_site_restriction(query: str) -> tuple[str, list[str]]:
    """Extract site: tokens into a domain list; returns (clean_query, domains)."""
    domains = _SITE_TOKEN_RE.findall(query)
    clean = _SITE_TOKEN_RE.sub("", query).strip()
    return clean, domains


class TavilySearchProvider:
    interface_version = "1.0.0"
    provider_code = "tavily"

    def __init__(self, api_key: str, poster: Poster | None = None) -> None:
        if not api_key:
            raise ValueError("tavily requires an API key")
        self._api_key = api_key
        self._post = poster or _default_poster

    def search(self, request: SearchQuery) -> SearchResponse:
        clean_query, domains = split_site_restriction(request.query)
        body: dict[str, Any] = {
            "query": clean_query or request.query,
            "max_results": min(request.max_results, MAX_RESULTS_PER_REQUEST),
            "search_depth": "basic",
        }
        if domains:
            body["include_domains"] = domains
        try:
            response = self._post(API_ENDPOINT, body, self._api_key)
        except urllib.error.HTTPError as exc:
            log.error("tavily_http_error", status=exc.code)
            status = (
                e.ProviderRequestStatus.RATE_LIMITED
                if exc.code == 429
                else e.ProviderRequestStatus.FAILED
            )
            return SearchResponse(status=status, error_code=f"HTTP_{exc.code}")
        except Exception as exc:  # noqa: BLE001 - transport errors become typed results
            log.error("tavily_transport_error", error=type(exc).__name__)
            return SearchResponse(
                status=e.ProviderRequestStatus.FAILED,
                error_code=f"TRANSPORT_{type(exc).__name__}",
            )

        items = [
            SearchResultItem(
                url=result["url"],
                title=result.get("title"),
                snippet=result.get("content"),
                rank=rank,
            )
            for rank, result in enumerate(response.get("results", []), start=1)
            if result.get("url")
        ]
        return SearchResponse(status=e.ProviderRequestStatus.SUCCEEDED, items=items)


def build_search_provider_from_settings(settings) -> TavilySearchProvider:
    providers = settings.providers
    api_key = (
        providers.search_provider_api_key.get_secret_value()
        if providers.search_provider_api_key
        else ""
    )
    return TavilySearchProvider(api_key)
