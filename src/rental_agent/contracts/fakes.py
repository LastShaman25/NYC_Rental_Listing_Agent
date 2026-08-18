"""Deterministic test doubles for every provider interface.

Automated tests never make live provider calls (PR-NFR-006). Each fake returns
configurable canned results and records the requests it received.
"""

from datetime import UTC, datetime
from typing import Any

from rental_agent.contracts import enums as e
from rental_agent.contracts.observation import ExtractionBlock, ParsedSourceObservation
from rental_agent.contracts.providers import (
    AcquisitionPartition,
    DiscoveredItem,
    DiscoveryPage,
    GeocodeRequest,
    GeocodeResult,
    LatLon,
    LlmTaskRequest,
    LlmTaskResult,
    MapRenderRequest,
    RawListingCapture,
    SearchQuery,
    SearchResponse,
    SourcePreflightResult,
    TransitDataset,
    TransitRouteResult,
    WalkingRouteResult,
)


class FakeGeocoder:
    interface_version = "1.0.0"
    provider_code = "fake_geocoder"

    def __init__(self, results: dict[str, GeocodeResult] | None = None) -> None:
        self.results = results or {}
        self.requests: list[GeocodeRequest] = []

    def geocode(self, request: GeocodeRequest) -> GeocodeResult:
        self.requests.append(request)
        if request.formatted_address in self.results:
            return self.results[request.formatted_address]
        return GeocodeResult(
            status=e.ProviderRequestStatus.FAILED, error_code="NOT_CONFIGURED_IN_FAKE"
        )


class FakeRouter:
    interface_version = "1.0.0"
    provider_code = "fake_router"

    def __init__(
        self,
        walk: WalkingRouteResult | None = None,
        transit: TransitRouteResult | None = None,
    ) -> None:
        self.walk_result = walk or WalkingRouteResult(
            status=e.ProviderRequestStatus.FAILED, error_code="NOT_CONFIGURED_IN_FAKE"
        )
        self.transit_result = transit or TransitRouteResult(
            status=e.ProviderRequestStatus.FAILED,
            result_status=e.CommuteResultStatus.PROVIDER_ERROR,
            error_code="NOT_CONFIGURED_IN_FAKE",
        )
        self.walk_requests: list[tuple[LatLon, LatLon]] = []
        self.transit_requests: list[tuple[LatLon, LatLon, datetime]] = []

    def walk_route(self, origin: LatLon, destination: LatLon) -> WalkingRouteResult:
        self.walk_requests.append((origin, destination))
        return self.walk_result

    def transit_route(
        self, origin: LatLon, destination: LatLon, depart_at: datetime
    ) -> TransitRouteResult:
        self.transit_requests.append((origin, destination, depart_at))
        return self.transit_result


class FakeTransitDatasetLoader:
    interface_version = "1.0.0"
    provider_code = "fake_transit_data"

    def __init__(self, datasets: dict[tuple[str, str], TransitDataset] | None = None) -> None:
        self.datasets = datasets or {}

    def load(self, operator_code: str, dataset_version: str) -> TransitDataset:
        key = (operator_code, dataset_version)
        if key in self.datasets:
            return self.datasets[key]
        return TransitDataset(operator_code=operator_code, dataset_version=dataset_version)


class FakeLlmExecutor:
    interface_version = "1.0.0"
    provider_code = "fake_llm"

    def __init__(self, outputs: dict[str, dict[str, Any]] | None = None) -> None:
        self.outputs = outputs or {}  # keyed by task_type
        self.requests: list[LlmTaskRequest] = []

    def execute(self, request: LlmTaskRequest) -> LlmTaskResult:
        self.requests.append(request)
        if request.task_type in self.outputs:
            return LlmTaskResult(
                status=e.ModelExecutionStatus.SUCCEEDED,
                output=self.outputs[request.task_type],
                confidence=e.Confidence.HIGH,
                model_id="fake-model-1",
            )
        return LlmTaskResult(
            status=e.ModelExecutionStatus.FAILED, error_code="NOT_CONFIGURED_IN_FAKE"
        )


class FakeSourceAdapter:
    """Fixture-driven adapter double for the acquisition pipeline."""

    interface_version = "1.0.0"
    source_code = "fake_source"
    adapter_version = "0.0.1"

    def __init__(
        self,
        observations: list[ParsedSourceObservation] | None = None,
        preflight_result: str = "READY",
    ) -> None:
        self.observations = observations or []
        self.preflight_result = preflight_result

    def preflight(self, context: dict[str, Any]) -> SourcePreflightResult:
        return SourcePreflightResult(result=self.preflight_result)

    def plan_partitions(self, context: dict[str, Any]) -> list[AcquisitionPartition]:
        return [
            AcquisitionPartition(source_code=self.source_code, partition_key="all", geography="ALL")
        ]

    def discover(
        self, partition: AcquisitionPartition, cursor: dict[str, Any] | None
    ) -> DiscoveryPage:
        return DiscoveryPage(
            items=[
                DiscoveredItem(source_native_id=o.source_native_id, detail_url=o.source_url)
                for o in self.observations
            ]
        )

    def fetch_detail(self, item: DiscoveredItem) -> RawListingCapture:
        obs = self._find(item.detail_url)
        return RawListingCapture(
            final_url=obs.source_url,
            retrieved_at=obs.retrieved_at,
            content_hash=f"fake-{hash(obs.source_url) & 0xFFFFFFFF:08x}",
        )

    def extract(self, capture: RawListingCapture) -> ParsedSourceObservation:
        return self._find(capture.final_url)

    def _find(self, url: str) -> ParsedSourceObservation:
        for o in self.observations:
            if o.source_url == url:
                return o
        raise KeyError(url)


class FakeSearchProvider:
    interface_version = "1.0.0"
    provider_code = "fake_search"

    def __init__(self, responses: dict[str, "SearchResponse"] | None = None) -> None:
        self.responses = responses or {}
        self.queries: list[SearchQuery] = []

    def search(self, request: SearchQuery) -> "SearchResponse":
        self.queries.append(request)
        if request.query in self.responses:
            return self.responses[request.query]
        return SearchResponse(
            status=e.ProviderRequestStatus.FAILED, error_code="NOT_CONFIGURED_IN_FAKE"
        )


class FakeMapAdapter:
    interface_version = "1.0.0"
    provider_code = "fake_map"

    def __init__(self) -> None:
        self.rendered: list[MapRenderRequest] = []

    def render(self, request: MapRenderRequest) -> dict[str, Any]:
        self.rendered.append(request)
        return {"markers": len(request.markers)}


def minimal_observation(
    source_url: str = "https://example.test/listing/1",
    source_native_id: str | None = "L1",
    observed_at: datetime | None = None,
) -> ParsedSourceObservation:
    """Convenience factory for tests."""
    now = observed_at or datetime.now(tz=UTC)
    return ParsedSourceObservation(
        source_code="fake_source",
        source_native_id=source_native_id,
        source_url=source_url,
        observed_at=now,
        retrieved_at=now,
        extraction=ExtractionBlock(adapter_version="0.0.1"),
    )
