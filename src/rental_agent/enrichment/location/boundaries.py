"""Boundary loading and geographic scope validation (04 §9).

Sources (both official, keyless):
- NYC borough boundaries: NYC Open Data GeoJSON export.
- NJ municipalities (Jersey City, Hoboken, Fort Lee): US Census TIGERweb
  incorporated-places layer, GeoJSON output.

Scope validation sets address.boundary_status from polygon intersection —
IN_SCOPE / OUT_OF_SCOPE for located addresses, UNRESOLVED preserved for
unlocated ones. Never derived from source neighborhood text (PR-GEO-001).
"""

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from rental_agent.config.logging import get_logger
from rental_agent.db.models import GeographicBoundary

log = get_logger(__name__)

# NYC official Borough Boundary FeatureServer (ArcGIS, keyless).
NYC_BOROUGHS_URL = (
    "https://services5.arcgis.com/GfwWNkhOj9bNBqoJ/arcgis/rest/services/"
    "NYC_Borough_Boundary/FeatureServer/0/query"
    "?where=1%3D1&outFields=BoroName&returnGeometry=true&f=geojson"
)
# TIGERweb layer 4 = Incorporated Places (verified 2026-08-17).
TIGERWEB_PLACES_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/"
    "Places_CouSub_ConCity_SubMCD/MapServer/4/query"
)
NJ_PLACES = {"Jersey City": "NJ_JERSEY_CITY", "Hoboken": "NJ_HOBOKEN", "Fort Lee": "NJ_FORT_LEE"}


def _fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": "rental-agent/0.1 (internal)"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - https only
        return json.loads(response.read().decode("utf-8"))


def upsert_boundary(
    session: Session,
    *,
    region_code: str,
    display_name: str,
    region_group: str,
    geometry_geojson: dict[str, Any],
    dataset_version: str,
) -> bool:
    """Insert a boundary from GeoJSON geometry; returns False if code exists."""
    exists = session.execute(
        select(GeographicBoundary.geographic_boundary_id).where(
            GeographicBoundary.region_code == region_code
        )
    ).scalar_one_or_none()
    if exists is not None:
        return False
    session.execute(
        text(
            "INSERT INTO config.geographic_boundary "
            "(region_code, display_name, region_group, geometry, dataset_version) "
            "VALUES (:code, :name, :grp, "
            "ST_Multi(ST_MakeValid(ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326)))::geography, "
            ":version)"
        ),
        {
            "code": region_code,
            "name": display_name,
            "grp": region_group,
            "geojson": json.dumps(geometry_geojson),
            "version": dataset_version,
        },
    )
    return True


def load_nyc_boroughs(session: Session, dataset_version: str) -> int:
    body = _fetch_json(NYC_BOROUGHS_URL)
    added = 0
    for feature in body.get("features", []):
        name = feature["properties"].get("BoroName") or feature["properties"].get("boro_name")
        if not name:
            continue
        code = f"NYC_{name.upper().replace(' ', '_')}"
        if upsert_boundary(
            session,
            region_code=code,
            display_name=f"{name} (NYC)",
            region_group="NYC",
            geometry_geojson=feature["geometry"],
            dataset_version=dataset_version,
        ):
            added += 1
    return added


def load_nj_places(session: Session, dataset_version: str) -> int:
    # TIGERweb NAME carries legal suffixes ("Hoboken city"); BASENAME is bare.
    # STATE='34' (NJ) matters — Georgia also has a Hoboken.
    names = "','".join(NJ_PLACES)
    url = (
        TIGERWEB_PLACES_URL
        + "?"
        + urllib.parse.urlencode(
            {
                "where": f"BASENAME IN ('{names}') AND STATE = '34'",
                "outFields": "BASENAME",
                "returnGeometry": "true",
                "f": "geojson",
            }
        )
    )
    body = _fetch_json(url)
    added = 0
    for feature in body.get("features", []):
        name = feature["properties"].get("BASENAME")
        code = NJ_PLACES.get(name)
        if code is None:
            continue
        if upsert_boundary(
            session,
            region_code=code,
            display_name=f"{name}, NJ",
            region_group="NJ",
            geometry_geojson=feature["geometry"],
            dataset_version=dataset_version,
        ):
            added += 1
    return added


@dataclass
class ScopeRunSummary:
    evaluated: int = 0
    in_scope: int = 0
    out_of_scope: int = 0
    by_region: dict[str, int] = field(default_factory=dict)


def validate_boundaries(session: Session, limit: int = 1000) -> ScopeRunSummary:
    """Set boundary_status for located addresses from polygon intersection.

    Refuses to run with an empty registry: absence of boundary data must never
    convert unknown scope into OUT_OF_SCOPE (PR-GEO-001 safety default).
    """
    summary = ScopeRunSummary()
    boundary_count = session.execute(
        text("SELECT count(*) FROM config.geographic_boundary")
    ).scalar_one()
    if not boundary_count:
        log.error("boundary_validation_refused", reason="no boundaries loaded")
        return summary
    rows = session.execute(
        text(
            "SELECT a.address_id, b.region_code "
            "FROM app.address a "
            "LEFT JOIN config.geographic_boundary b "
            "  ON ST_Intersects(b.geometry, a.location_point) "
            "WHERE a.location_point IS NOT NULL AND a.boundary_status = 'UNRESOLVED' "
            "LIMIT :limit"
        ),
        {"limit": limit},
    ).all()
    for address_id, region_code in rows:
        status = "IN_SCOPE" if region_code else "OUT_OF_SCOPE"
        session.execute(
            text("UPDATE app.address SET boundary_status = :status WHERE address_id = :id"),
            {"status": status, "id": address_id},
        )
        summary.evaluated += 1
        if region_code:
            summary.in_scope += 1
            summary.by_region[region_code] = summary.by_region.get(region_code, 0) + 1
        else:
            summary.out_of_scope += 1
    log.info(
        "boundary_validation",
        evaluated=summary.evaluated,
        in_scope=summary.in_scope,
        out_of_scope=summary.out_of_scope,
    )
    return summary
