"""Geocoding service: fill coordinates for addresses that lack them (04 §8).

Chain: NYC GeoSearch first (all current listings are NYC), Census fallback.
Each attempt records an idempotent ops.provider_request row; the address gets
coordinates + honest precision + geocoder provenance. Addresses with the
"[address unresolved]" placeholder are skipped — no coordinate is ever invented.
Boundary polygon validation (04 §9) is a later increment; boundary_status stays
UNRESOLVED until then.
"""

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from rental_agent.config.logging import get_logger
from rental_agent.contracts import enums as e
from rental_agent.contracts.providers import Geocoder, GeocodeRequest
from rental_agent.db.models import Address, ProviderRequest, Source

log = get_logger(__name__)


@dataclass
class GeocodeRunSummary:
    attempted: int = 0
    geocoded: int = 0
    failed: int = 0
    skipped_unresolved: int = 0
    by_provider: dict[str, int] = field(default_factory=dict)


class GeocodeService:
    def __init__(self, session: Session, geocoders: list[Geocoder]) -> None:
        """geocoders are tried in order; first success wins."""
        self._s = session
        self._geocoders = geocoders
        self._source_ids: dict[str, uuid.UUID] = {}

    def _source_id(self, provider_code: str) -> uuid.UUID:
        if provider_code not in self._source_ids:
            source = self._s.execute(
                select(Source).where(Source.source_code == provider_code)
            ).scalar_one_or_none()
            if source is None:
                source = Source(
                    source_code=provider_code,
                    display_name=provider_code,
                    source_type=e.SourceType.GEOCODER.value,
                    access_method=e.AccessMethod.API.value,
                    approval_status=e.SourceApprovalStatus.APPROVED.value,
                    enabled=True,
                    policy_version="free-open-1",
                )
                self._s.add(source)
                self._s.flush()
            self._source_ids[provider_code] = source.source_id
        return self._source_ids[provider_code]

    def geocode_address(self, address: Address) -> bool:
        """Geocode one address in place; returns True when coordinates landed."""
        if not address.address_line_1:
            return False
        query_text = f"{address.address_line_1}, {address.locality}, "
        query_text += address.administrative_area
        request = GeocodeRequest(
            formatted_address=query_text,
            locality=address.locality,
            administrative_area=address.administrative_area,
        )
        now = datetime.now(tz=UTC)
        for geocoder in self._geocoders:
            result = geocoder.geocode(request)  # network call; no open transaction
            self._record_request(geocoder.provider_code, query_text, result, now)
            if result.status is not e.ProviderRequestStatus.SUCCEEDED:
                continue
            address.location_point = f"SRID=4326;POINT({result.longitude} {result.latitude})"
            address.location_precision = result.precision.value
            address.geocoder_source_id = self._source_id(geocoder.provider_code)
            address.geocoder_result_id = result.provider_result_id
            address.geocoded_at = now
            address.geocode_input_hash = hashlib.sha256(query_text.encode()).hexdigest()
            address.geocode_status = e.GeocodeStatus.VALID.value
            if result.components.get("borough"):
                address.borough = result.components["borough"]
            return True
        address.geocode_status = e.GeocodeStatus.FAILED.value
        return False

    def _record_request(self, provider_code, query_text, result, now) -> None:
        self._s.execute(
            pg_insert(ProviderRequest)
            .values(
                source_id=self._source_id(provider_code),
                request_type=e.ProviderRequestType.GEOCODE.value,
                request_hash=hashlib.sha256(query_text.encode()).hexdigest(),
                request_parameters={"text": query_text},
                provider_result_id=result.provider_result_id,
                status=result.status.value,
                requested_at=now,
                completed_at=now,
                error_code=result.error_code,
            )
            .on_conflict_do_nothing()
        )

    def geocode_pending(self, limit: int = 500) -> GeocodeRunSummary:
        """Geocode all addresses lacking coordinates. Placeholder addresses are
        skipped: an unresolved address must never be placed at a guess."""
        summary = GeocodeRunSummary()
        addresses = (
            self._s.execute(
                select(Address)
                .where(
                    Address.location_point.is_(None),
                    Address.geocode_status != e.GeocodeStatus.FAILED.value,
                )
                .limit(limit)
            )
            .scalars()
            .all()
        )
        for address in addresses:
            if not address.address_line_1 or address.formatted_address.startswith(
                "[address unresolved]"
            ):
                summary.skipped_unresolved += 1
                continue
            summary.attempted += 1
            if self.geocode_address(address):
                summary.geocoded += 1
                source = (
                    self._s.get(Source, address.geocoder_source_id)
                    if address.geocoder_source_id
                    else None
                )
                code = source.source_code if source is not None else "unknown"
                summary.by_provider[code] = summary.by_provider.get(code, 0) + 1
            else:
                summary.failed += 1
        log.info(
            "geocode_run",
            attempted=summary.attempted,
            geocoded=summary.geocoded,
            failed=summary.failed,
            skipped=summary.skipped_unresolved,
        )
        return summary
