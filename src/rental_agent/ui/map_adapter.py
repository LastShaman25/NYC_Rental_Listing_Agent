"""Leaflet map adapter via folium (08 §4; MapAdapter interface).

The initial map approach is Leaflet through streamlit-folium behind this
replaceable adapter (owner constraint). Tile provider is configuration; the
default OSM tiles are the agent-recommended placeholder until the Phase 8 tile
decision. No paid map APIs are used (B7).
"""

from typing import Any

import folium
from folium.plugins import Draw, MarkerCluster

from rental_agent.contracts.providers import MapRenderRequest

NYC_DEFAULT_CENTER = (40.73, -73.99)


class FoliumMapAdapter:
    interface_version = "1.0.0"
    provider_code = "folium_leaflet"

    def __init__(self, tile_provider_code: str = "osm_default") -> None:
        # osm_default -> folium's built-in OpenStreetMap tiles.
        self._tiles = "OpenStreetMap" if tile_provider_code == "osm_default" else tile_provider_code

    def render(self, request: MapRenderRequest) -> Any:
        center = (
            (request.center.latitude, request.center.longitude)
            if request.center
            else NYC_DEFAULT_CENTER
        )
        fmap = folium.Map(location=center, zoom_start=request.zoom or 12, tiles=self._tiles)
        Draw(
            export=False,
            draw_options={
                "polygon": True,
                "rectangle": True,
                "circle": False,
                "marker": False,
                "polyline": False,
                "circlemarker": False,
            },
        ).add_to(fmap)
        cluster = MarkerCluster(name="listings").add_to(fmap)
        for marker in request.markers:
            state = marker.state or {}
            label = state.get("label", marker.listing_id)
            approx = marker.precision.value not in (
                "ROOFTOP_OR_ENTRANCE",
                "BUILDING",
                "PARCEL",
            )
            folium.Marker(
                location=(marker.latitude, marker.longitude),
                tooltip=f"{label}{' (approximate location)' if approx else ''}",
                popup=folium.Popup(html=state.get("popup_html", label), max_width=300),
                icon=folium.Icon(
                    color="blue" if state.get("selected") else "gray",
                    icon="home",
                    prefix="fa",
                ),
            ).add_to(cluster)
        if request.drawn_geometry_geojson:
            folium.GeoJson(
                request.drawn_geometry_geojson,
                name="filter-area",
                style_function=lambda _f: {"fillOpacity": 0.08, "color": "#3388ff"},
            ).add_to(fmap)
        return fmap
