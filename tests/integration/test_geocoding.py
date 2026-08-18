"""Geocoder wire mapping + geocode service behavior (04 §8; PR-LOC-001)."""

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from tests.conftest import requires_db

from rental_agent.contracts import enums as e
from rental_agent.contracts.providers import GeocodeRequest, GeocodeResult
from rental_agent.db.models import Address, ProviderRequest
from rental_agent.enrichment.location.geocoders import CensusGeocoder, NycGeosearchGeocoder
from rental_agent.enrichment.location.service import GeocodeService

pytestmark = requires_db


def test_geosearch_maps_point_exact_to_rooftop():
    def fetch(url):
        return {
            "features": [
                {
                    "geometry": {"coordinates": [-73.9776, 40.7451]},
                    "properties": {
                        "id": "node/1",
                        "label": "225 East 34th Street, Manhattan, NY",
                        "accuracy": "point",
                        "match_type": "exact",
                        "borough": "Manhattan",
                    },
                }
            ]
        }

    result = NycGeosearchGeocoder(fetcher=fetch).geocode(
        GeocodeRequest(formatted_address="225 East 34th Street, Manhattan, NY")
    )
    assert result.status is e.ProviderRequestStatus.SUCCEEDED
    assert result.precision is e.LocationPrecision.ROOFTOP_OR_ENTRANCE
    assert (round(result.longitude, 4), round(result.latitude, 4)) == (-73.9776, 40.7451)


def test_geosearch_no_match_is_typed_failure():
    result = NycGeosearchGeocoder(fetcher=lambda url: {"features": []}).geocode(
        GeocodeRequest(formatted_address="nowhere")
    )
    assert result.status is e.ProviderRequestStatus.FAILED
    assert result.error_code == "NO_MATCH"


def test_census_never_claims_rooftop():
    def fetch(url):
        return {
            "result": {
                "addressMatches": [
                    {
                        "coordinates": {"x": -74.03, "y": 40.74},
                        "matchedAddress": "1 CASTLE POINT TER, HOBOKEN, NJ",
                        "tigerLine": {"tigerLineId": "123"},
                    }
                ]
            }
        }

    result = CensusGeocoder(fetcher=fetch).geocode(
        GeocodeRequest(formatted_address="1 Castle Point Terrace, Hoboken, NJ")
    )
    assert result.status is e.ProviderRequestStatus.SUCCEEDED
    assert result.precision is e.LocationPrecision.INTERPOLATED_ADDRESS


class StubGeocoder:
    interface_version = "1.0.0"

    def __init__(self, provider_code: str, result: GeocodeResult) -> None:
        self.provider_code = provider_code
        self.result = result
        self.calls: list[GeocodeRequest] = []

    def geocode(self, request: GeocodeRequest) -> GeocodeResult:
        self.calls.append(request)
        return self.result


SUCCESS = GeocodeResult(
    status=e.ProviderRequestStatus.SUCCEEDED,
    latitude=40.75,
    longitude=-73.98,
    precision=e.LocationPrecision.BUILDING,
    provider_result_id="r1",
)
FAILURE = GeocodeResult(status=e.ProviderRequestStatus.FAILED, error_code="NO_MATCH")


@pytest.fixture()
def pending_addresses(db_session: Session):
    rows = [
        Address(
            address_line_1="100 Real Street",
            locality="Manhattan",
            administrative_area="NY",
            formatted_address="100 Real Street",
        ),
        Address(
            locality="UNRESOLVED",
            administrative_area="NY",
            formatted_address="[address unresolved] https://x.test/1",
        ),
    ]
    db_session.add_all(rows)
    db_session.commit()
    return rows


def test_service_geocodes_pending_and_skips_placeholders(db_session: Session, pending_addresses):
    primary = StubGeocoder("nyc_geosearch", SUCCESS)
    service = GeocodeService(db_session, [primary])
    summary = service.geocode_pending()
    db_session.commit()

    assert summary.attempted == 1
    assert summary.geocoded == 1
    assert summary.skipped_unresolved == 1  # placeholder never placed at a guess
    real, placeholder = pending_addresses
    assert real.geocode_status == "VALID"
    assert real.location_precision == "BUILDING"
    assert placeholder.location_point is None
    lon = db_session.execute(
        text("SELECT ST_X(location_point::geometry) FROM app.address WHERE address_id = :id"),
        {"id": real.address_id},
    ).scalar_one()
    assert round(lon, 2) == -73.98
    # Provider request recorded for audit.
    assert db_session.execute(select(func.count()).select_from(ProviderRequest)).scalar() == 1


def test_service_falls_back_to_second_geocoder(db_session: Session, pending_addresses):
    primary = StubGeocoder("nyc_geosearch", FAILURE)
    fallback = StubGeocoder("census_geocoder", SUCCESS)
    service = GeocodeService(db_session, [primary, fallback])
    summary = service.geocode_pending()
    db_session.commit()
    assert summary.geocoded == 1
    assert summary.by_provider == {"census_geocoder": 1}
    assert len(primary.calls) == 1 and len(fallback.calls) == 1


def test_all_failures_mark_address_failed_not_guessed(db_session: Session, pending_addresses):
    service = GeocodeService(db_session, [StubGeocoder("nyc_geosearch", FAILURE)])
    summary = service.geocode_pending()
    db_session.commit()
    assert summary.failed == 1
    real, _ = pending_addresses
    assert real.geocode_status == "FAILED"
    assert real.location_point is None  # no fabricated coordinates, ever
