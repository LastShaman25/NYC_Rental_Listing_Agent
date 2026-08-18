"""Nearby-transit candidate generation (04 §11).

For each geocoded listing, finds station complexes within the configured
per-mode straight-line radii using PostGIS and stores them as transit_access
CANDIDATE rows with proximity ranks. Honesty rules:

- Only straight-line distance is stored; walking distance/time stay NULL until
  a walking router exists (04 §12 — straight-line is never presented as walking).
- usefulness_status stays CANDIDATE/UNRESOLVED until usefulness rules (04 §13)
  are implemented; validation stays PENDING.
- Rows are keyed by input_location_hash: re-running with an unchanged origin
  replaces nothing; a moved origin invalidates and regenerates.
"""

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from rental_agent.config.logging import get_logger
from rental_agent.contracts import enums as e
from rental_agent.db.models import Address, Building, CanonicalListing, TransitAccess

log = get_logger(__name__)

# Initial candidate radii in meters (04 §11.2); calibration inputs, not "nearby" claims.
CANDIDATE_RADII_M = {
    e.TransitMode.SUBWAY: 1600,
    e.TransitMode.PATH: 2000,
}
MAX_CANDIDATES_PER_MODE = 5


@dataclass
class NearbyRunSummary:
    listings_processed: int = 0
    listings_skipped_no_point: int = 0
    access_rows_created: int = 0
    by_mode: dict[str, int] = field(default_factory=dict)


class NearbyTransitService:
    def __init__(self, session: Session) -> None:
        self._s = session

    def enrich_listing(self, canonical_listing_id: uuid.UUID) -> int:
        """Generate candidate rows for one listing; returns rows created."""
        row = self._s.execute(
            text(
                "SELECT a.address_id, ST_X(a.location_point::geometry) AS lon, "
                "ST_Y(a.location_point::geometry) AS lat, a.location_precision "
                "FROM app.canonical_listing cl "
                "JOIN app.building b ON b.building_id = cl.building_id "
                "JOIN app.address a ON a.address_id = b.address_id "
                "WHERE cl.canonical_listing_id = :id AND a.location_point IS NOT NULL"
            ),
            {"id": canonical_listing_id},
        ).first()
        if row is None:
            return 0
        # Low-precision origins never produce exact-looking claims (04 §8.4);
        # candidates are still allowed for BUILDING and better.
        location_hash = hashlib.sha256(
            f"{row.lon:.6f},{row.lat:.6f},{row.location_precision},radii-v1".encode()
        ).hexdigest()

        existing = self._s.execute(
            select(TransitAccess.input_location_hash)
            .where(TransitAccess.canonical_listing_id == canonical_listing_id)
            .limit(1)
        ).scalar_one_or_none()
        if existing == location_hash:
            return 0  # unchanged origin: reuse (04 §23.3)
        if existing is not None:
            # Origin changed: prior results are invalid (02 §21).
            self._s.execute(
                delete(TransitAccess).where(
                    TransitAccess.canonical_listing_id == canonical_listing_id
                )
            )

        created = 0
        now = datetime.now(tz=UTC)
        for mode, radius in CANDIDATE_RADII_M.items():
            # Station complexes only: stops with no parent (platform rows carry
            # parent_stop_id), within radius, nearest first.
            stops = self._s.execute(
                text(
                    "SELECT transit_stop_id, dataset_version, "
                    "ST_Distance(location_point, "
                    "  ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS meters "
                    "FROM app.transit_stop "
                    "WHERE mode = :mode AND parent_stop_id IS NULL "
                    "  AND active_status = 'ACTIVE' "
                    "  AND ST_DWithin(location_point, "
                    "      ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :radius) "
                    "ORDER BY meters ASC LIMIT :limit"
                ),
                {
                    "lon": row.lon,
                    "lat": row.lat,
                    "mode": mode.value,
                    "radius": radius,
                    "limit": MAX_CANDIDATES_PER_MODE,
                },
            ).all()
            for rank, stop in enumerate(stops, start=1):
                self._s.add(
                    TransitAccess(
                        canonical_listing_id=canonical_listing_id,
                        transit_stop_id=stop.transit_stop_id,
                        mode=mode.value,
                        straight_line_distance_m=int(stop.meters),
                        proximity_rank=rank,
                        usefulness_status=e.UsefulnessStatus.CANDIDATE.value,
                        validation_status=e.TransitValidationStatus.PENDING.value,
                        input_location_hash=location_hash,
                        dataset_version=stop.dataset_version,
                        calculated_at=now,
                    )
                )
                created += 1
        self._s.flush()
        return created

    def enrich_all_geocoded(self, limit: int = 500) -> NearbyRunSummary:
        summary = NearbyRunSummary()
        listing_ids = (
            self._s.execute(
                select(CanonicalListing.canonical_listing_id)
                .join(Building, Building.building_id == CanonicalListing.building_id)
                .join(Address, Address.address_id == Building.address_id)
                .where(Address.location_point.is_not(None))
                .limit(limit)
            )
            .scalars()
            .all()
        )
        for listing_id in listing_ids:
            created = self.enrich_listing(listing_id)
            summary.listings_processed += 1
            summary.access_rows_created += created
        log.info(
            "nearby_transit_run",
            listings=summary.listings_processed,
            rows=summary.access_rows_created,
        )
        return summary
