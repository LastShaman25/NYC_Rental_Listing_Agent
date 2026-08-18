"""Routed walking access for primary transit candidates (04 §12).

Uses the FOSSGIS OSRM foot-profile server (community OSM routing, keyless,
fair-use — we route only rank-1 candidates, paced). Plausibility checks per
04 §12.2: routed distance must not undercut straight-line beyond tolerance,
and implied speed must fall in the pedestrian band, else WARNING. Provider
failures leave walking fields NULL — a straight-line number is never promoted
into a walking claim.
"""

import json
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from rental_agent.config.logging import get_logger
from rental_agent.contracts import enums as e

log = get_logger(__name__)

OSRM_FOOT_URL = "https://routing.openstreetmap.de/routed-foot/route/v1/foot"
WALK_SPEED_MIN_MPS = 0.5
WALK_SPEED_MAX_MPS = 2.2
GEOMETRY_TOLERANCE_M = 30

Fetcher = Callable[[str], dict[str, Any]]


def _default_fetcher(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url, headers={"User-Agent": "rental-agent/0.1 (internal, low-volume)"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - https only
        return json.loads(response.read().decode("utf-8"))


class OsrmFootRouter:
    interface_version = "1.0.0"
    provider_code = "osrm_foot_fossgis"

    def __init__(self, fetcher: Fetcher | None = None) -> None:
        self._fetch = fetcher or _default_fetcher

    def walk_route(self, origin_lon, origin_lat, dest_lon, dest_lat) -> tuple[int, int] | None:
        """Returns (distance_m, duration_s) or None on any failure."""
        url = (
            f"{OSRM_FOOT_URL}/{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
            "?overview=false&alternatives=false"
        )
        try:
            body = self._fetch(url)
        except Exception as exc:  # noqa: BLE001 - provider failure leaves fields NULL
            log.warning("osrm_error", error=type(exc).__name__)
            return None
        routes = body.get("routes") or []
        if body.get("code") != "Ok" or not routes:
            return None
        route = routes[0]
        return int(route["distance"]), int(route["duration"])


@dataclass
class WalkingRunSummary:
    attempted: int = 0
    routed: int = 0
    warnings: int = 0
    failed: int = 0


class WalkingEnrichmentService:
    """Routes walking for rank-1 candidates lacking walking data."""

    def __init__(
        self, session: Session, router: OsrmFootRouter, *, pace_seconds: float = 1.0
    ) -> None:
        self._s = session
        self._router = router
        self._pace = pace_seconds

    def enrich_primary_candidates(self, limit: int = 200) -> WalkingRunSummary:
        summary = WalkingRunSummary()
        rows = self._s.execute(
            text(
                "SELECT ta.transit_access_id, ta.straight_line_distance_m, "
                "ST_X(a.location_point::geometry) AS olon, "
                "ST_Y(a.location_point::geometry) AS olat, "
                "ST_X(ts.location_point::geometry) AS dlon, "
                "ST_Y(ts.location_point::geometry) AS dlat "
                "FROM app.transit_access ta "
                "JOIN app.canonical_listing cl "
                "  ON cl.canonical_listing_id = ta.canonical_listing_id "
                "JOIN app.building b ON b.building_id = cl.building_id "
                "JOIN app.address a ON a.address_id = b.address_id "
                "JOIN app.transit_stop ts ON ts.transit_stop_id = ta.transit_stop_id "
                "WHERE ta.proximity_rank = 1 AND ta.walking_distance_m IS NULL "
                "  AND a.location_point IS NOT NULL "
                "LIMIT :limit"
            ),
            {"limit": limit},
        ).all()
        for row in rows:
            summary.attempted += 1
            result = self._router.walk_route(row.olon, row.olat, row.dlon, row.dlat)
            time.sleep(self._pace)  # fair-use pacing for the community server
            if result is None:
                summary.failed += 1
                continue
            distance_m, duration_s = result
            validation = e.TransitValidationStatus.PASSED
            reasons: dict[str, Any] = {"router": self._router.provider_code}
            straight = row.straight_line_distance_m or 0
            if distance_m + GEOMETRY_TOLERANCE_M < straight:
                validation = e.TransitValidationStatus.WARNING
                reasons["issue"] = "routed_shorter_than_straight_line"
            elif duration_s > 0:
                speed = distance_m / duration_s
                if not (WALK_SPEED_MIN_MPS <= speed <= WALK_SPEED_MAX_MPS):
                    validation = e.TransitValidationStatus.WARNING
                    reasons["issue"] = f"implausible_speed_{speed:.2f}mps"
            if validation is e.TransitValidationStatus.WARNING:
                summary.warnings += 1
            self._s.execute(
                text(
                    "UPDATE app.transit_access SET walking_distance_m = :d, "
                    "walking_duration_s = :s, validation_status = :v, "
                    "validation_reasons = CAST(:r AS jsonb) "
                    "WHERE transit_access_id = :id"
                ),
                {
                    "d": distance_m,
                    "s": duration_s,
                    "v": validation.value,
                    "r": json.dumps(reasons),
                    "id": row.transit_access_id,
                },
            )
            summary.routed += 1
        log.info(
            "walking_run",
            attempted=summary.attempted,
            routed=summary.routed,
            warnings=summary.warnings,
            failed=summary.failed,
        )
        return summary
