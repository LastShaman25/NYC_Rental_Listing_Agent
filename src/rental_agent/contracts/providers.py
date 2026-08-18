"""Versioned provider interfaces (00 §11, 04 §5.1, 08 §4).

Every external dependency — listing sources, geocoding, walking/transit routing,
transit datasets, LLMs, map rendering — sits behind one of these Protocols.
Canonical business logic depends only on these interfaces; provider identity is
configuration. Test doubles live in rental_agent.contracts.fakes.
"""

from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from rental_agent.contracts import enums as e
from rental_agent.contracts.observation import ParsedSourceObservation

PROVIDER_INTERFACE_VERSION = "1.0.0"


# --- Geocoding (04 §8) -------------------------------------------------------


class GeocodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    formatted_address: str
    locality: str | None = None
    administrative_area: str | None = None
    postal_code: str | None = None


class GeocodeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: e.ProviderRequestStatus
    latitude: float | None = None
    longitude: float | None = None
    precision: e.LocationPrecision = e.LocationPrecision.UNKNOWN
    provider_result_id: str | None = None
    formatted_address: str | None = None
    components: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None


class Geocoder(Protocol):
    interface_version: str
    provider_code: str

    def geocode(self, request: GeocodeRequest) -> GeocodeResult: ...


# --- Walking and transit routing (04 §5.1, §20) ------------------------------


class LatLon(BaseModel):
    model_config = ConfigDict(extra="forbid")
    latitude: float
    longitude: float


class WalkingRouteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: e.ProviderRequestStatus
    distance_m: int | None = Field(default=None, ge=0)
    duration_s: int | None = Field(default=None, ge=0)
    provider_result_id: str | None = None
    error_code: str | None = None


class TransitRouteLeg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: str
    operator: str | None = None
    route_label: str | None = None
    board_stop: str | None = None
    alight_stop: str | None = None
    duration_s: int | None = Field(default=None, ge=0)
    distance_m: int | None = Field(default=None, ge=0)


class TransitRouteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: e.ProviderRequestStatus
    result_status: e.CommuteResultStatus = e.CommuteResultStatus.UNAVAILABLE
    duration_s: int | None = Field(default=None, ge=0)
    distance_m: int | None = Field(default=None, ge=0)
    transfer_count: int | None = Field(default=None, ge=0)
    legs: list[TransitRouteLeg] = Field(default_factory=list)
    provider_result_id: str | None = None
    error_code: str | None = None


class Router(Protocol):
    interface_version: str
    provider_code: str

    def walk_route(self, origin: LatLon, destination: LatLon) -> WalkingRouteResult: ...

    def transit_route(
        self, origin: LatLon, destination: LatLon, depart_at: datetime
    ) -> TransitRouteResult: ...


# --- Transit datasets (04 §10) -----------------------------------------------


class TransitDatasetStop(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_stop_id: str
    parent_provider_stop_id: str | None = None
    operator_code: str
    stop_name: str
    mode: e.TransitMode
    latitude: float
    longitude: float
    route_provider_ids: list[str] = Field(default_factory=list)


class TransitDatasetRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_route_id: str
    operator_code: str
    route_short_name: str | None = None
    route_long_name: str | None = None
    mode: e.TransitMode


class TransitDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operator_code: str
    dataset_version: str
    stops: list[TransitDatasetStop] = Field(default_factory=list)
    routes: list[TransitDatasetRoute] = Field(default_factory=list)


class TransitDatasetLoader(Protocol):
    interface_version: str
    provider_code: str

    def load(self, operator_code: str, dataset_version: str) -> TransitDataset: ...


# --- LLM execution (02 §11, 03 §10.4) ----------------------------------------


class LlmTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_type: str
    prompt_version: str
    output_schema_version: str
    input_refs: dict[str, Any]
    input_payload: dict[str, Any]
    output_schema: dict[str, Any] | None = None  # JSON Schema the output must match
    tier: e.ModelTier = e.ModelTier.DEFAULT_HOSTED


class LlmTaskResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: e.ModelExecutionStatus
    output: dict[str, Any] | None = None
    confidence: e.Confidence = e.Confidence.UNKNOWN
    model_id: str = ""
    input_tokens: int | None = None
    output_tokens: int | None = None
    error_code: str | None = None


class LlmExecutor(Protocol):
    interface_version: str
    provider_code: str

    def execute(self, request: LlmTaskRequest) -> LlmTaskResult: ...


# --- Web-search provider (03 §5.4, owner decision B3) ------------------------


class SearchQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str  # e.g. 'site:streeteasy.com "1 bedroom" "Hoboken"'
    max_results: int = Field(default=20, ge=1, le=100)


class SearchResultItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str
    title: str | None = None
    snippet: str | None = None
    rank: int | None = None


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: e.ProviderRequestStatus
    items: list[SearchResultItem] = Field(default_factory=list)
    provider_result_id: str | None = None
    error_code: str | None = None


class SearchProvider(Protocol):
    """Configurable web-search index used for search-based listing discovery.

    Absence of a listing from search results is never disappearance evidence.
    """

    interface_version: str
    provider_code: str

    def search(self, request: SearchQuery) -> SearchResponse: ...


# --- Listing-source adapter (03 §7.1) ----------------------------------------


class SourcePreflightResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    result: str  # READY | DEGRADED | BLOCKED
    reasons: list[str] = Field(default_factory=list)


class AcquisitionPartition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_code: str
    partition_key: str
    geography: str
    layout: str | None = None
    query_parameters: dict[str, Any] = Field(default_factory=dict)
    cursor_state: dict[str, Any] | None = None


class DiscoveredItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_native_id: str | None = None
    detail_url: str
    card_facts: dict[str, Any] = Field(default_factory=dict)


class DiscoveryPage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[DiscoveredItem] = Field(default_factory=list)
    next_cursor: dict[str, Any] | None = None
    appears_truncated: bool = False
    health_markers: dict[str, Any] = Field(default_factory=dict)


class RawListingCapture(BaseModel):
    model_config = ConfigDict(extra="forbid")
    final_url: str
    retrieved_at: datetime
    content_hash: str
    structured_blocks: dict[str, Any] = Field(default_factory=dict)
    visible_content_ref: str | None = None
    structural_signature: str | None = None


class SourceAdapter(Protocol):
    """One approved listing source. Adapters never write canonical records,
    never mark listings inactive, and never touch selection state (03 §21.2)."""

    interface_version: str
    source_code: str
    adapter_version: str

    def preflight(self, context: dict[str, Any]) -> SourcePreflightResult: ...

    def plan_partitions(self, context: dict[str, Any]) -> list[AcquisitionPartition]: ...

    def discover(
        self, partition: AcquisitionPartition, cursor: dict[str, Any] | None
    ) -> DiscoveryPage: ...

    def fetch_detail(self, item: DiscoveredItem) -> RawListingCapture: ...

    def extract(self, capture: RawListingCapture) -> ParsedSourceObservation: ...


# --- Map rendering adapter (08 §4: Leaflet/streamlit-folium initially) -------


class MapMarker(BaseModel):
    model_config = ConfigDict(extra="forbid")
    listing_id: str
    latitude: float
    longitude: float
    precision: e.LocationPrecision
    state: dict[str, Any] = Field(default_factory=dict)


class MapRenderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    markers: list[MapMarker] = Field(default_factory=list)
    center: LatLon | None = None
    zoom: int | None = None
    drawn_geometry_geojson: dict[str, Any] | None = None


class MapAdapter(Protocol):
    interface_version: str
    provider_code: str

    def render(self, request: MapRenderRequest) -> Any: ...
