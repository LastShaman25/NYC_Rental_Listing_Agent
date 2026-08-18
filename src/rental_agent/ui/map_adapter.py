"""Leaflet map adapter via folium (08 §4; MapAdapter interface).

The initial map approach is Leaflet through streamlit-folium behind this
replaceable adapter (owner constraint). Tile provider is configuration; the
CartoDB Positron tiles give the desaturated basemap the Kinetic Mapview design
calls for (md/DESIGN.md); no paid map APIs are used (B7).

Markers follow the DESIGN.md component spec: rectangular 4px-radius badges with
a colored left-accent bar (blue = shortlisted/selected, green = active, amber =
warning, slate = other) and a compact Inter bold label.
"""

from typing import Any

import folium
from folium.plugins import Draw, MarkerCluster

from rental_agent.contracts.providers import MapRenderRequest
from rental_agent.ui.theme import marker_accent

NYC_DEFAULT_CENTER = (40.73, -73.99)

_MARKER_HTML = (
    '<div style="display:flex;align-items:stretch;background:rgba(255,255,255,0.92);'
    "border:1px solid #E2E8F0;border-radius:4px;box-shadow:0 1px 3px rgba(0,0,0,0.08);"
    'white-space:nowrap;width:max-content;">'
    '<span style="width:3px;border-radius:4px 0 0 4px;background:{accent};"></span>'
    '<span style="padding:2px 6px;font:700 10px/12px Inter,-apple-system,sans-serif;'
    'color:#191c1e;">{label}</span></div>'
)


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
        fmap = folium.Map(
            location=center,
            zoom_start=request.zoom or 12,
            tiles="CartoDB positron" if self._tiles == "OpenStreetMap" else self._tiles,
        )
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
            badge = _MARKER_HTML.format(accent=marker_accent(state), label=label)
            folium.Marker(
                location=(marker.latitude, marker.longitude),
                tooltip=f"{label}{' (approximate location)' if approx else ''}",
                popup=folium.Popup(html=state.get("popup_html", label), max_width=300),
                icon=folium.DivIcon(html=badge, icon_size=(0, 0), icon_anchor=(0, 10)),
            ).add_to(cluster)
        if request.drawn_geometry_geojson:
            folium.GeoJson(
                request.drawn_geometry_geojson,
                name="filter-area",
                style_function=lambda _f: {"fillOpacity": 0.08, "color": "#3388ff"},
            ).add_to(fmap)
        return fmap
