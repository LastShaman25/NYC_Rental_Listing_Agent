"""GTFS static dataset loader (04 §10; Phase 4).

Parses a GTFS zip's ``stops.txt`` and ``routes.txt`` into the normalized
TransitDataset contract and ingests them idempotently into ``app.transit_stop``
/ ``app.transit_route`` under a dataset version. Trip/stop-time topology
(needed for full route-topology validation and stop↔route relations) is a later
Phase 4 increment — station/route name cross-checks work with this much.

Feeds are downloaded by the caller under each operator's approved terms; this
module never fabricates coordinates or service data.
"""

import csv
import io
import uuid
import zipfile
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from rental_agent.config.logging import get_logger
from rental_agent.contracts import enums as e
from rental_agent.contracts.providers import (
    TransitDataset,
    TransitDatasetRoute,
    TransitDatasetStop,
)
from rental_agent.db.models import TransitRoute, TransitStop

log = get_logger(__name__)

# GTFS route_type → normalized mode (04 §10.1). Operator override handles PATH,
# which publishes as subway-typed but is its own mode in this product.
ROUTE_TYPE_TO_MODE = {
    "0": e.TransitMode.OTHER,  # tram/light rail
    "1": e.TransitMode.SUBWAY,
    "2": e.TransitMode.RAIL,
    "3": e.TransitMode.BUS,
    "4": e.TransitMode.FERRY,
}


def parse_gtfs_zip(
    zip_path: Path,
    *,
    operator_code: str,
    dataset_version: str,
    mode_override: e.TransitMode | None = None,
) -> TransitDataset:
    """Parse stops.txt + routes.txt from a GTFS zip without full extraction."""
    stops: list[TransitDatasetStop] = []
    routes: list[TransitDatasetRoute] = []
    with zipfile.ZipFile(zip_path) as archive:
        with archive.open("routes.txt") as f:
            for row in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig")):
                mode = mode_override or ROUTE_TYPE_TO_MODE.get(
                    (row.get("route_type") or "").strip(), e.TransitMode.OTHER
                )
                routes.append(
                    TransitDatasetRoute(
                        provider_route_id=row["route_id"].strip(),
                        operator_code=operator_code,
                        route_short_name=(row.get("route_short_name") or "").strip() or None,
                        route_long_name=(row.get("route_long_name") or "").strip() or None,
                        mode=mode,
                    )
                )
        with archive.open("stops.txt") as f:
            for row in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig")):
                lat, lon = (row.get("stop_lat") or "").strip(), (row.get("stop_lon") or "").strip()
                if not lat or not lon:
                    continue  # never fabricate a coordinate
                # location_type 0/blank = stop/platform, 1 = parent station.
                stops.append(
                    TransitDatasetStop(
                        provider_stop_id=row["stop_id"].strip(),
                        parent_provider_stop_id=(row.get("parent_station") or "").strip() or None,
                        operator_code=operator_code,
                        stop_name=(row.get("stop_name") or "").strip() or row["stop_id"].strip(),
                        mode=mode_override or (routes[0].mode if routes else e.TransitMode.OTHER),
                        latitude=float(lat),
                        longitude=float(lon),
                    )
                )
    return TransitDataset(
        operator_code=operator_code,
        dataset_version=dataset_version,
        stops=stops,
        routes=routes,
    )


def ingest_dataset(
    session: Session, dataset: TransitDataset, *, provider_source_id: uuid.UUID
) -> dict[str, int]:
    """Idempotent ingest under (provider_source_id, provider_id, dataset_version).

    Parent-station links resolve in a second pass so file order never matters.
    """
    stops_inserted = routes_inserted = 0
    for route in dataset.routes:
        result = session.execute(
            pg_insert(TransitRoute)
            .values(
                provider_source_id=provider_source_id,
                provider_route_id=route.provider_route_id,
                operator_code=route.operator_code,
                route_short_name=route.route_short_name,
                route_long_name=route.route_long_name,
                mode=route.mode.value,
                dataset_version=dataset.dataset_version,
            )
            .on_conflict_do_nothing()
            .returning(TransitRoute.transit_route_id)
        )
        if result.scalar_one_or_none() is not None:
            routes_inserted += 1

    for stop in dataset.stops:
        result = session.execute(
            pg_insert(TransitStop)
            .values(
                provider_source_id=provider_source_id,
                provider_stop_id=stop.provider_stop_id,
                operator_code=stop.operator_code,
                stop_name=stop.stop_name,
                mode=stop.mode.value,
                location_point=f"SRID=4326;POINT({stop.longitude} {stop.latitude})",
                active_status=e.TransitStopActiveStatus.ACTIVE.value,
                dataset_version=dataset.dataset_version,
            )
            .on_conflict_do_nothing()
            .returning(TransitStop.transit_stop_id)
        )
        if result.scalar_one_or_none() is not None:
            stops_inserted += 1
    session.flush()

    # Second pass: parent-station relationships.
    id_by_provider = {
        provider_id: stop_id
        for provider_id, stop_id in session.execute(
            select(TransitStop.provider_stop_id, TransitStop.transit_stop_id).where(
                TransitStop.provider_source_id == provider_source_id,
                TransitStop.dataset_version == dataset.dataset_version,
            )
        )
    }
    linked = 0
    for stop in dataset.stops:
        if not stop.parent_provider_stop_id:
            continue
        child = id_by_provider.get(stop.provider_stop_id)
        parent = id_by_provider.get(stop.parent_provider_stop_id)
        if child is None or parent is None:
            continue
        row = session.get(TransitStop, child)
        if row is not None and row.parent_stop_id is None:
            row.parent_stop_id = parent
            linked += 1
    session.flush()
    counts = {
        "stops_inserted": stops_inserted,
        "routes_inserted": routes_inserted,
        "parents_linked": linked,
    }
    log.info("gtfs_ingested", operator=dataset.operator_code, **counts)
    return counts
