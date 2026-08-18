"""Free/open geocoder implementations (04 §8; B7: no paid Google APIs).

- NycGeosearchGeocoder: NYC Planning GeoSearch (geosearch.planninglabs.nyc),
  official NYC open data, keyless. Authoritative for the five boroughs.
- CensusGeocoder: US Census Bureau geocoder, keyless, covers NY + NJ; results
  are typically street-interpolated (honest lower precision).

Both sit behind the Geocoder Protocol with injectable transports; failures map
to typed results, and precision is never overstated (PR-LOC-001).
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

from rental_agent.config.logging import get_logger
from rental_agent.contracts import enums as e
from rental_agent.contracts.providers import GeocodeRequest, GeocodeResult

log = get_logger(__name__)

Fetcher = Callable[[str], dict[str, Any]]


def _default_fetcher(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": "rental-agent/0.1 (internal)"}
    )
    with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 - https only
        return json.loads(response.read().decode("utf-8"))


class NycGeosearchGeocoder:
    interface_version = "1.0.0"
    provider_code = "nyc_geosearch"
    ENDPOINT = "https://geosearch.planninglabs.nyc/v2/search"

    def __init__(self, fetcher: Fetcher | None = None) -> None:
        self._fetch = fetcher or _default_fetcher

    def geocode(self, request: GeocodeRequest) -> GeocodeResult:
        url = (
            self.ENDPOINT
            + "?"
            + urllib.parse.urlencode({"text": request.formatted_address, "size": 1})
        )
        try:
            body = self._fetch(url)
        except Exception as exc:  # noqa: BLE001 - transport errors become typed results
            log.error("geosearch_error", error=type(exc).__name__)
            return GeocodeResult(
                status=e.ProviderRequestStatus.FAILED,
                error_code=f"TRANSPORT_{type(exc).__name__}",
            )
        features = body.get("features") or []
        if not features:
            return GeocodeResult(status=e.ProviderRequestStatus.FAILED, error_code="NO_MATCH")
        feature = features[0]
        lon, lat = feature["geometry"]["coordinates"]
        properties = feature.get("properties", {})
        # Pelias accuracy: "point" = rooftop-quality; "centroid" = area centroid.
        accuracy = properties.get("accuracy")
        match_type = properties.get("match_type")
        if accuracy == "point" and match_type == "exact":
            precision = e.LocationPrecision.ROOFTOP_OR_ENTRANCE
        elif accuracy == "point":
            precision = e.LocationPrecision.BUILDING
        elif match_type == "interpolated":
            precision = e.LocationPrecision.INTERPOLATED_ADDRESS
        else:
            precision = e.LocationPrecision.NEIGHBORHOOD
        return GeocodeResult(
            status=e.ProviderRequestStatus.SUCCEEDED,
            latitude=lat,
            longitude=lon,
            precision=precision,
            provider_result_id=properties.get("id"),
            formatted_address=properties.get("label"),
            components={
                "borough": properties.get("borough"),
                "postalcode": properties.get("postalcode"),
                "accuracy": accuracy,
                "match_type": match_type,
            },
        )


class CensusGeocoder:
    interface_version = "1.0.0"
    provider_code = "census_geocoder"
    ENDPOINT = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"

    def __init__(self, fetcher: Fetcher | None = None) -> None:
        self._fetch = fetcher or _default_fetcher

    def geocode(self, request: GeocodeRequest) -> GeocodeResult:
        url = (
            self.ENDPOINT
            + "?"
            + urllib.parse.urlencode(
                {
                    "address": request.formatted_address,
                    "benchmark": "Public_AR_Current",
                    "format": "json",
                }
            )
        )
        try:
            body = self._fetch(url)
        except Exception as exc:  # noqa: BLE001
            log.error("census_geocoder_error", error=type(exc).__name__)
            return GeocodeResult(
                status=e.ProviderRequestStatus.FAILED,
                error_code=f"TRANSPORT_{type(exc).__name__}",
            )
        matches = (body.get("result") or {}).get("addressMatches") or []
        if not matches:
            return GeocodeResult(status=e.ProviderRequestStatus.FAILED, error_code="NO_MATCH")
        match = matches[0]
        coordinates = match["coordinates"]
        return GeocodeResult(
            status=e.ProviderRequestStatus.SUCCEEDED,
            latitude=coordinates["y"],
            longitude=coordinates["x"],
            # Census results are TIGER street-interpolated; never claim rooftop.
            precision=e.LocationPrecision.INTERPOLATED_ADDRESS,
            formatted_address=match.get("matchedAddress"),
            components={"tigerLineId": (match.get("tigerLine") or {}).get("tigerLineId")},
        )
