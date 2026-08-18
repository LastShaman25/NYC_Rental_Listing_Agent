"""Database-level invariants from 02 §8.3, §12.3, §16.3 (schema acceptance tests)."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from tests.conftest import requires_db

pytestmark = requires_db

NOW = datetime.now(tz=UTC)


def _listing_kwargs(building_id):
    return dict(
        building_id=building_id,
        first_seen_at=NOW,
        last_seen_at=NOW,
        last_material_change_at=NOW,
    )


def test_postgis_available(db_session: Session):
    version = db_session.execute(text("SELECT postgis_version()")).scalar_one()
    assert version.startswith("3.")


def test_laundry_badge_check_constraint(db_session: Session, seeded_listing):
    from rental_agent.db.models import CanonicalListing

    listing = db_session.get(CanonicalListing, seeded_listing)
    listing.laundry_type = "BUILDING_SHARED_LAUNDRY"
    listing.indoor_laundry_badge_eligible = True
    with pytest.raises(IntegrityError, match="laundry_badge_invariant"):
        db_session.commit()
    db_session.rollback()

    listing = db_session.get(CanonicalListing, seeded_listing)
    listing.laundry_type = "IN_UNIT_WASHER_DRYER_CONFIRMED"
    listing.indoor_laundry_badge_eligible = True
    db_session.commit()


def test_negative_rent_rejected(db_session: Session, seeded_listing):
    from rental_agent.db.models import CanonicalListing

    listing = db_session.get(CanonicalListing, seeded_listing)
    listing.monthly_rent_minor = -1
    with pytest.raises(IntegrityError, match="rent_nonnegative"):
        db_session.commit()
    db_session.rollback()


def test_invalid_enum_value_rejected_by_database(db_session: Session, seeded_listing):
    # Raw SQL bypasses ORM-side enum validation, exercising the CHECK itself.
    with pytest.raises(IntegrityError, match="lifecycle_status_enum"):
        db_session.execute(
            text(
                "UPDATE app.canonical_listing SET lifecycle_status = 'TOTALLY_INVALID' "
                "WHERE canonical_listing_id = :id"
            ),
            {"id": seeded_listing},
        )
        db_session.commit()
    db_session.rollback()


def test_invalid_enum_value_rejected_by_orm(db_session: Session, seeded_listing):
    from sqlalchemy.exc import StatementError

    from rental_agent.db.models import CanonicalListing

    listing = db_session.get(CanonicalListing, seeded_listing)
    listing.lifecycle_status = "TOTALLY_INVALID"
    with pytest.raises(StatementError):
        db_session.commit()
    db_session.rollback()


def test_single_current_fact_resolution(db_session: Session, seeded_listing):
    from rental_agent.db.models import FactResolution

    def make():
        return FactResolution(
            entity_type="LISTING",
            entity_id=seeded_listing,
            fact_key="laundry_type",
            resolution_status="RESOLVED",
            resolution_method="RULE",
            resolution_rule_version="r1",
        )

    db_session.add(make())
    db_session.commit()
    db_session.add(make())
    with pytest.raises(IntegrityError, match="uq_fact_resolution_current"):
        db_session.commit()
    db_session.rollback()

    # A superseded resolution does not block a new current one.
    from sqlalchemy import update

    from rental_agent.db.models import FactResolution as FR

    db_session.execute(update(FR).values(superseded_at=NOW))
    db_session.add(make())
    db_session.commit()


def test_commute_available_requires_duration(db_session: Session, seeded_listing, seeded_source):
    from rental_agent.db.models import CommuteResult, Destination, ProviderRequest

    dest = Destination(
        destination_code=f"TEST_DEST_{uuid.uuid4().hex[:6]}",
        destination_type="MAJOR_DESTINATION",
        display_name="Test",
        routing_anchor_name="Test anchor",
        routing_anchor_point="SRID=4326;POINT(-73.98 40.75)",
        registry_version="v1",
    )
    req = ProviderRequest(
        source_id=seeded_source,
        request_type="TRANSIT_ROUTE",
        request_hash=uuid.uuid4().hex,
        request_parameters={},
        requested_at=NOW,
    )
    db_session.add_all([dest, req])
    db_session.flush()
    result = CommuteResult(
        canonical_listing_id=seeded_listing,
        destination_id=dest.destination_id,
        provider_request_id=req.provider_request_id,
        time_basis="DEPART_AT",
        result_status="AVAILABLE",
        duration_s=None,  # must fail: AVAILABLE requires a duration
        input_location_hash="h1",
        destination_registry_version="v1",
        calculated_at=NOW,
    )
    db_session.add(result)
    with pytest.raises(IntegrityError, match="available_requires_duration"):
        db_session.commit()
    db_session.rollback()


def test_geography_point_roundtrip(db_session: Session):
    from rental_agent.db.models import Address

    address = Address(
        locality="Hoboken",
        administrative_area="NJ",
        formatted_address="1 Castle Point Terrace, Hoboken, NJ",
        location_point="SRID=4326;POINT(-74.0247 40.7440)",
    )
    db_session.add(address)
    db_session.commit()
    lon, lat = db_session.execute(
        text(
            "SELECT ST_X(location_point::geometry), ST_Y(location_point::geometry) "
            "FROM app.address WHERE address_id = :id"
        ),
        {"id": address.address_id},
    ).one()
    assert (round(lon, 4), round(lat, 4)) == (-74.0247, 40.7440)


def test_spatial_indexes_exist(db_session: Session):
    rows = db_session.execute(
        text(
            "SELECT tablename, indexname FROM pg_indexes "
            "WHERE schemaname = 'app' AND indexdef ILIKE '%%gist%%'"
        )
    ).all()
    indexed_tables = {r.tablename for r in rows}
    assert {"address", "transit_stop", "destination", "client_search_preset"} <= indexed_tables


def test_observation_idempotency_unique_index(db_session: Session, seeded_source):
    from rental_agent.db.models import RefreshRun, SourceObservation, SourceRun

    run = RefreshRun(
        trigger_type="MANUAL",
        logical_run_key=f"test:{uuid.uuid4().hex}",
        started_at=NOW,
        pipeline_version="t1",
    )
    db_session.add(run)
    db_session.flush()
    source_run = SourceRun(
        refresh_run_id=run.refresh_run_id,
        source_id=seeded_source,
        started_at=NOW,
        adapter_version="t1",
    )
    db_session.add(source_run)
    db_session.flush()

    def make():
        return SourceObservation(
            source_id=seeded_source,
            source_run_id=source_run.source_run_id,
            source_native_id="N1",
            source_url="https://example.test/1",
            observed_at=NOW,
            retrieved_at=NOW,
            content_hash="h1",
            parsed_payload={},
            parse_status="VALID",
            contact_redaction_status="NOT_PRESENT",
            adapter_version="t1",
            schema_version="1.0.0",
        )

    db_session.add(make())
    db_session.commit()
    db_session.add(make())
    with pytest.raises(IntegrityError, match="uq_source_observation_native_identity"):
        db_session.commit()
    db_session.rollback()


def test_marketing_selection_one_row_per_listing(db_session: Session, seeded_listing):
    from rental_agent.db.models import MarketingSelection

    def make():
        return MarketingSelection(
            canonical_listing_id=seeded_listing,
            selection_status="SELECTED",
            selected_by="local_operator",
            selected_at=NOW,
        )

    db_session.add(make())
    db_session.commit()
    db_session.add(make())
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
