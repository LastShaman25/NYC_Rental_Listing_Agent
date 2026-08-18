from rental_agent.contracts.enums import LocationPrecision
from rental_agent.contracts.providers import MapMarker, MapRenderRequest
from rental_agent.ui.map_adapter import FoliumMapAdapter


def _marker(listing_id: str, precision=LocationPrecision.BUILDING) -> MapMarker:
    return MapMarker(
        listing_id=listing_id,
        latitude=40.73,
        longitude=-73.99,
        precision=precision,
        state={"label": f"listing {listing_id}"},
    )


def test_render_produces_folium_map_with_cluster_and_draw():
    fmap = FoliumMapAdapter().render(MapRenderRequest(markers=[_marker("a"), _marker("b")]))
    html = fmap.get_root().render()
    assert "MarkerCluster" in html or "markerCluster" in html
    assert "leaflet.draw" in html or "Draw" in html
    assert html.count("listing ") >= 2


def test_low_precision_marker_labeled_approximate():
    fmap = FoliumMapAdapter().render(
        MapRenderRequest(markers=[_marker("x", LocationPrecision.NEIGHBORHOOD)])
    )
    assert "approximate location" in fmap.get_root().render()


def test_drawn_geometry_rendered():
    geojson = {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[-74.05, 40.7], [-73.9, 40.7], [-73.9, 40.8], [-74.05, 40.7]]],
        },
    }
    fmap = FoliumMapAdapter().render(MapRenderRequest(markers=[], drawn_geometry_geojson=geojson))
    html = fmap.get_root().render()
    assert "geo_json" in html or "GeoJson" in html
    assert "-74.05" in html  # the drawn polygon's coordinates made it to the page
