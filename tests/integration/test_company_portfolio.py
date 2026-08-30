"""Company portfolio: availability service (link repair, geocode, building
match) and the webui portal (upload, listing, LLM config)."""

import uuid
import zipfile
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from tests.conftest import requires_db
from tests.unit.test_company_file_parse import _DOC_XML, _RELS_XML

from rental_agent.canonical.normalization import address_fingerprint
from rental_agent.contracts import enums as e
from rental_agent.contracts.providers import (
    LlmTaskResult,
    SearchResponse,
    SearchResultItem,
)
from rental_agent.db.models import Address, Building, CompanyProperty
from rental_agent.enrichment.company.service import CompanyAvailabilityService
from rental_agent.webui.app import create_app

pytestmark = [pytest.mark.integration, requires_db]


class _FakeExtract:
    def __init__(self, pages: dict[str, str | None]) -> None:
        self._pages = pages

    def extract(self, url: str) -> str | None:
        return self._pages.get(url)


class _FakeSearch:
    def __init__(self, urls: list[str]) -> None:
        self._urls = urls

    def search(self, request):  # noqa: ANN001, ANN201 - protocol shape
        return SearchResponse(
            status=e.ProviderRequestStatus.SUCCEEDED,
            items=[SearchResultItem(url=u, rank=i) for i, u in enumerate(self._urls)],
        )


class _FakeLlm:
    def __init__(self, output: dict) -> None:
        self._output = output

    def execute(self, request):  # noqa: ANN001, ANN201
        return LlmTaskResult(status=e.ModelExecutionStatus.SUCCEEDED, output=self._output)


class _FakeGeocoder:
    provider_code = "fake_geocoder"

    def geocode(self, request):  # noqa: ANN001, ANN201
        from rental_agent.contracts.providers import GeocodeResult

        return GeocodeResult(
            status=e.ProviderRequestStatus.SUCCEEDED,
            latitude=40.72,
            longitude=-73.95,
            precision=e.LocationPrecision.BUILDING,
        )


_AVAILABILITY = {
    "page_is_this_property": True,
    "address": "12 Franklin Street",
    "locality": "Brooklyn",
    "available_units": [
        {
            "unit_label": "4B",
            "layout": "1BR",
            "monthly_rent_usd": 3400,
            "availability_text": "Available now",
        }
    ],
    "no_units_stated": False,
    "evidence": "Unit 4B — available now, $3,400/mo",
}


def _make_prop(session: Session, **kw) -> CompanyProperty:
    prop = CompanyProperty(
        name=kw.pop("name", "The Greenpoint"),
        name_fingerprint=kw.pop("name_fingerprint", f"the greenpoint {uuid.uuid4().hex[:6]}"),
        source_document="portfolio.docx",
        **kw,
    )
    session.add(prop)
    session.flush()
    return prop


def test_working_link_checks_availability_and_matches_building(db_engine) -> None:
    with Session(db_engine) as session:
        address = Address(
            address_line_1="12 Franklin Street",
            locality="Brooklyn",
            administrative_area="NY",
            formatted_address="12 Franklin Street",
            address_fingerprint=address_fingerprint("12 Franklin Street"),
        )
        session.add(address)
        session.flush()
        building = Building(address_id=address.address_id)
        session.add(building)
        session.flush()
        prop = _make_prop(session, original_url="https://example.com/greenpoint")
        service = CompanyAvailabilityService(
            session,
            _FakeLlm(_AVAILABILITY),
            _FakeExtract({"https://example.com/greenpoint": "Greenpoint page $3,400 available"}),
            geocoders=[_FakeGeocoder()],
        )
        assert service.check(prop) == "CHECKED"
        assert prop.link_status == "OK"
        assert prop.resolved_url == "https://example.com/greenpoint"
        assert prop.availability["available_units"][0]["monthly_rent_usd"] == 3400
        assert prop.address_text == "12 Franklin Street"
        assert prop.latitude == 40.72  # geocoded, never guessed
        assert prop.matched_building_id == building.building_id
        session.rollback()


def test_dead_link_repaired_via_official_site(db_engine) -> None:
    with Session(db_engine) as session:
        prop = _make_prop(session, original_url="https://dead.example.com/gone")
        service = CompanyAvailabilityService(
            session,
            _FakeLlm(_AVAILABILITY),
            _FakeExtract(
                {
                    "https://dead.example.com/gone": None,
                    # Aggregator result must be skipped; official site wins.
                    "https://thegreenpoint.com/": "Welcome to The Greenpoint leasing",
                }
            ),
            search_provider=_FakeSearch(
                ["https://streeteasy.com/building/x", "https://thegreenpoint.com/"]
            ),
            geocoders=[],
        )
        assert service.check(prop) == "CHECKED"
        assert prop.link_status == "REPLACED"
        assert prop.resolved_url == "https://thegreenpoint.com/"
        assert prop.resolved_url_kind == "OFFICIAL_SITE"
        session.rollback()


def test_address_named_property_geocodes_even_when_page_fails(db_engine) -> None:
    """Name-in-file is a street address ('160 water st'): the property must
    still be geocoded and mappable when its page is unreachable."""
    with Session(db_engine) as session:
        prop = _make_prop(
            session, name="160 water st", original_url="https://dead.example.com/gone"
        )
        service = CompanyAvailabilityService(
            session,
            _FakeLlm(_AVAILABILITY),
            _FakeExtract({}),
            search_provider=_FakeSearch([]),
            geocoders=[_FakeGeocoder()],
        )
        assert service.check(prop) == "FAILED"
        assert prop.address_text == "160 water st"  # name doubles as address
        assert prop.latitude == 40.72  # mapped despite the dead page
        session.rollback()


def test_streeteasy_building_fallback_captures_page_name(db_engine) -> None:
    """Address-named property with a dead link: the StreetEasy fallback must
    prefer /building/ pages over blog posts, and the page-stated marketing
    name ('Pearl House') is captured."""
    building_url = "https://streeteasy.com/building/pearl-house-seaport"
    with Session(db_engine) as session:
        prop = _make_prop(
            session, name="160 water st", original_url="https://dead.example.com/gone"
        )
        service = CompanyAvailabilityService(
            session,
            _FakeLlm(
                {
                    **_AVAILABILITY,
                    "property_name": "Pearl House",
                    "address": "160 Water Street",
                    "locality": "Financial District",
                }
            ),
            _FakeExtract(
                {building_url: "Pearl House at 160 Water Street — available units"}
            ),
            search_provider=_FakeSearch(
                ["https://streeteasy.com/blog/some-roundup", building_url]
            ),
            geocoders=[],
        )
        assert service.check(prop) == "CHECKED"
        assert prop.resolved_url == building_url
        assert prop.resolved_url_kind == "STREETEASY"
        assert prop.availability["page_property_name"] == "Pearl House"
        session.rollback()


def test_all_sources_failing_is_honest(db_engine) -> None:
    with Session(db_engine) as session:
        prop = _make_prop(session, original_url="https://dead.example.com/gone")
        prop.availability = {"available_units": [{"layout": "1BR"}], "checked_at": "x"}
        service = CompanyAvailabilityService(
            session,
            _FakeLlm(_AVAILABILITY),
            _FakeExtract({}),
            search_provider=_FakeSearch([]),
        )
        # Ordinary checks keep the last successful snapshot on failure...
        assert service.check(prop) == "FAILED"
        assert prop.link_status == "FAILED"
        assert prop.check_status == "FAILED"
        assert prop.availability is not None
        # ...but a full "Re-check all" sweep discards it (owner 2026-08-30).
        assert service.check(prop, discard_stale=True) == "FAILED"
        assert prop.availability is None
        session.rollback()


def test_check_log_records_history_events(db_engine) -> None:
    """Every completed check appends to the rolling history — first check,
    price changes, failures (the company analogue of listing events)."""
    with Session(db_engine) as session:
        prop = _make_prop(session, original_url="https://example.com/hist")
        service = CompanyAvailabilityService(
            session,
            _FakeLlm(_AVAILABILITY),
            _FakeExtract({"https://example.com/hist": "Greenpoint page $3,400 available"}),
        )
        assert service.check(prop) == "CHECKED"
        assert prop.check_log[0]["event"] == "FIRST_CHECK"
        assert prop.check_log[0]["min_rent"] == 3400
        # Same result again → UNCHANGED.
        assert service.check(prop) == "CHECKED"
        assert prop.check_log[0]["event"] == "UNCHANGED"
        # Rent change → PRICE_CHANGED.
        service_new_price = CompanyAvailabilityService(
            session,
            _FakeLlm(
                {
                    **_AVAILABILITY,
                    "available_units": [
                        {
                            "unit_label": "4B",
                            "layout": "1BR",
                            "monthly_rent_usd": 3600,
                            "availability_text": "Now",
                        }
                    ],
                }
            ),
            _FakeExtract({"https://example.com/hist": "Greenpoint page $3,600 available"}),
        )
        assert service_new_price.check(prop) == "CHECKED"
        assert prop.check_log[0]["event"] == "PRICE_CHANGED"
        # Failure → CHECK_FAILED entry, history preserved.
        service_dead = CompanyAvailabilityService(
            session, _FakeLlm(_AVAILABILITY), _FakeExtract({}), search_provider=_FakeSearch([])
        )
        assert service_dead.check(prop) == "FAILED"
        assert prop.check_log[0]["event"] == "CHECK_FAILED"
        assert len(prop.check_log) == 4
        session.rollback()


def test_provider_quota_error_never_touches_the_row(db_engine) -> None:
    """An exhausted Tavily plan (HTTP 432) must abort, not mass-fail: the
    check returns RATE_LIMITED and leaves the property exactly as it was
    (2026-08-30 incident: 164 properties were wrongly marked failed)."""
    from rental_agent.enrichment.listing_content.service import TavilyQuotaError

    class _QuotaExtract:
        def extract(self, url: str):  # noqa: ANN201
            raise TavilyQuotaError("plan usage limit reached")

    with Session(db_engine) as session:
        prop = _make_prop(session, original_url="https://example.com/x")
        prop.link_status = "OK"
        prop.check_status = "CHECKED"
        prop.availability = {"available_units": [{"layout": "1BR"}]}
        service = CompanyAvailabilityService(
            session, _FakeLlm(_AVAILABILITY), _QuotaExtract()
        )
        assert service.check(prop, discard_stale=True) == "RATE_LIMITED"
        assert prop.check_status == "CHECKED"  # untouched
        assert prop.link_status == "OK"
        assert prop.availability is not None
        session.rollback()


def test_company_property_shortlist_entry(db_engine) -> None:
    """Company properties join client shortlists through the same audited
    service as listings (owner request 2026-08-29)."""
    from rental_agent.canonical.selection_service import ClientShortlistService
    from rental_agent.contracts.enums import ActorType, ShortlistEntryStatus
    from rental_agent.ui import queries

    with Session(db_engine) as session:
        prop = _make_prop(session, address_text="160 Water Street")
        service = ClientShortlistService(session)
        preset = service.create_preset(
            label=f"company-sl-{uuid.uuid4().hex[:6]}",
            filter_definition={},
            filter_schema_version="1",
            actor="test_operator",
            actor_type=ActorType.HUMAN,
        )
        service.set_entry(
            client_search_preset_id=preset.client_search_preset_id,
            company_property_id=prop.company_property_id,
            status=ShortlistEntryStatus.INCLUDED,
            actor="test_operator",
            actor_type=ActorType.HUMAN,
            note="company pick",
        )
        entries = queries.shortlist_entries(session, preset.client_search_preset_id)
        company_rows = [e for e in entries if e["company_id"]]
        assert len(company_rows) == 1
        assert company_rows[0]["layout"] == "COMPANY"
        assert company_rows[0]["listing_id"] is None
        assert "160 Water Street" in company_rows[0]["address"]
        # Exactly one target is required — neither is rejected in code.
        with pytest.raises(ValueError):
            service.set_entry(
                client_search_preset_id=preset.client_search_preset_id,
                status=ShortlistEntryStatus.INCLUDED,
                actor="test_operator",
                actor_type=ActorType.HUMAN,
            )
        session.rollback()


def test_discard_inventory_preserves_company_portfolio(db_engine) -> None:
    """Full re-acquisition wipes ACQUIRED data only: company properties and
    their client-shortlist entries survive the TRUNCATE (owner report
    2026-08-29 — the building-FK cascade used to wipe them)."""
    from rental_agent.canonical.selection_service import ClientShortlistService
    from rental_agent.contracts.enums import ActorType, ShortlistEntryStatus
    from rental_agent.contracts.fakes import FakeLlmExecutor
    from rental_agent.db.models import ClientShortlistEntry, CommuteResult, Destination
    from rental_agent.enrichment.commute.research import (
        TASK_TYPE as COMMUTE_TASK,
    )
    from rental_agent.enrichment.commute.research import (
        CommuteResearchService,
    )
    from rental_agent.jobs.weekday_refresh import discard_inventory

    factory = sessionmaker(bind=db_engine, expire_on_commit=False)
    with factory() as session:
        address = Address(
            locality="Brooklyn", administrative_area="NY", formatted_address="9 Wipe Test St"
        )
        session.add(address)
        session.flush()
        building = Building(address_id=address.address_id)
        session.add(building)
        session.flush()
        prop = _make_prop(
            session,
            name="Wipe Survivor",
            name_fingerprint=f"wipe survivor {uuid.uuid4().hex[:6]}",
            matched_building_id=building.building_id,
        )
        service = ClientShortlistService(session)
        preset = service.create_preset(
            label=f"wipe-{uuid.uuid4().hex[:6]}",
            filter_definition={},
            filter_schema_version="1",
            actor="test_operator",
            actor_type=ActorType.HUMAN,
        )
        service.set_entry(
            client_search_preset_id=preset.client_search_preset_id,
            company_property_id=prop.company_property_id,
            status=ShortlistEntryStatus.INCLUDED,
            actor="test_operator",
            actor_type=ActorType.HUMAN,
        )
        # Destination anchor + researched company commute: both used to be
        # wiped through FK cascades (destination.address_id / ops.job chain).
        dest = Destination(
            destination_code=f"WIPE_{uuid.uuid4().hex[:6]}",
            destination_type="UNIVERSITY_CAMPUS",
            display_name="Wipe Campus",
            routing_anchor_name="Main hall",
            routing_anchor_point="SRID=4326;POINT(-73.99 40.73)",
            registry_version="v1",
        )
        session.add(dest)
        session.flush()
        CommuteResearchService(
            session,
            FakeLlmExecutor(
                outputs={
                    COMMUTE_TASK: {
                        "duration_min_s": 1200,
                        "duration_max_s": 1800,
                        "likely_routes": ["7"],
                        "transfer_count": 0,
                        "named_stations": [],
                        "summary": "quick",
                        "sources": [{"url": "https://example.test/g"}],
                        "confidence": "MEDIUM",
                    }
                }
            ),
            cache_days=14,
        ).research(
            company_property_id=prop.company_property_id,
            destination_id=dest.destination_id,
            origin_description="9 Wipe Test St, Brooklyn",
            input_location_hash="company:wipe",
        )
        prop_id = prop.company_property_id
        dest_id = dest.destination_id
        session.commit()

    discard_inventory(factory)

    with factory() as session:
        survivor = session.get(CompanyProperty, prop_id)
        assert survivor is not None, "company property must survive the wipe"
        assert survivor.matched_building_id is None  # buildings are gone
        entries = (
            session.execute(
                select(ClientShortlistEntry).where(
                    ClientShortlistEntry.company_property_id == prop_id
                )
            )
            .scalars()
            .all()
        )
        assert len(entries) == 1, "company shortlist entry must survive"
        restored_dest = session.get(Destination, dest_id)
        assert restored_dest is not None, "destination anchors must survive"
        assert restored_dest.address_id is None
        commutes = (
            session.execute(
                select(CommuteResult).where(
                    CommuteResult.company_property_id == prop_id
                )
            )
            .scalars()
            .all()
        )
        assert len(commutes) == 1, "company commute research must survive"
        assert session.execute(select(Building)).first() is None  # acquired graph wiped


# -- webui portal --------------------------------------------------------------


@pytest.fixture()
def client(migrated_engine, tmp_path) -> TestClient:
    factory = sessionmaker(bind=migrated_engine, expire_on_commit=False)
    settings = SimpleNamespace(
        operator_id="test_operator",
        paths=SimpleNamespace(raw=tmp_path, logs=tmp_path / "logs"),
    )
    app = create_app(factory=factory, settings=settings)
    return TestClient(app)


def _docx_bytes() -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", _DOC_XML)
        archive.writestr("word/_rels/document.xml.rels", _RELS_XML)
    return buffer.getvalue()


def test_company_page_renders(client: TestClient) -> None:
    response = client.get("/company")
    assert response.status_code == 200
    assert "Company Portfolio" in response.text


def test_upload_creates_rows_and_reupload_updates(client: TestClient, migrated_engine) -> None:
    files = {"file": ("portfolio.docx", _docx_bytes(), "application/octet-stream")}
    response = client.post("/actions/company-upload", files=files, follow_redirects=False)
    assert response.status_code == 303
    with Session(migrated_engine) as session:
        rows = session.execute(select(CompanyProperty)).scalars().all()
        names = {r.name for r in rows}
        assert "The Greenpoint" in names
        assert "Hudson Terrace Apartments" in names
        count_before = len(rows)
    # Re-upload: same names update in place, no duplicates.
    files = {"file": ("portfolio.docx", _docx_bytes(), "application/octet-stream")}
    client.post("/actions/company-upload", files=files, follow_redirects=False)
    with Session(migrated_engine) as session:
        rows = session.execute(select(CompanyProperty)).scalars().all()
        assert len(rows) == count_before
        session.execute(select(CompanyProperty)).scalars()
    page = client.get("/company").text
    assert "The Greenpoint" in page


def test_upload_rejects_other_file_types(client: TestClient) -> None:
    files = {"file": ("notes.txt", b"hello", "text/plain")}
    response = client.post("/actions/company-upload", files=files, follow_redirects=False)
    assert response.status_code == 303
    assert "error=" in response.headers["location"]


def test_llm_config_persists_to_env(client: TestClient, monkeypatch) -> None:
    captured: dict = {}

    def fake_update(path, values) -> None:
        captured.update(values)

    import rental_agent.config.env_file as env_file

    monkeypatch.setattr(env_file, "update_env_file", fake_update)
    response = client.post(
        "/actions/llm-config",
        data={"base_url": "https://openrouter.ai/api/v1", "model": "qwen-max"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "started=" in response.headers["location"]
    assert captured["RENTAL_PROVIDER_LLM_BASE_URL"] == "https://openrouter.ai/api/v1"
    assert captured["RENTAL_PROVIDER_LLM_DEFAULT_MODEL_ID"] == "qwen-max"
    # The route mirrors values into os.environ for spawned jobs — clean up.
    import os

    os.environ.pop("RENTAL_PROVIDER_LLM_BASE_URL", None)
    os.environ.pop("RENTAL_PROVIDER_LLM_DEFAULT_MODEL_ID", None)


def test_company_status_endpoint_reflects_job_heartbeat(client: TestClient, tmp_path) -> None:
    """The Company page's single live indicator reads the check job's status
    file: idle when absent, live progress while running, stalled when the
    heartbeat goes quiet."""
    from datetime import UTC, datetime, timedelta

    from rental_agent.jobs.company_refresh import status_path, write_status

    assert client.get("/api/company/status").json() == {"state": "idle"}
    path = status_path(tmp_path / "logs")
    write_status(
        path, state="running", total=167, done=42, counts={"CHECKED": 40}, current="Avalon"
    )
    data = client.get("/api/company/status").json()
    assert data["state"] == "running"
    assert data["done"] == 42 and data["total"] == 167
    assert data["current"] == "Avalon"
    assert data["stalled"] is False
    # A heartbeat older than 4 minutes marks the run as stalled.
    import json as _json

    stale = _json.loads(path.read_text(encoding="utf-8"))
    stale["updated_at"] = (datetime.now(tz=UTC) - timedelta(minutes=10)).isoformat()
    path.write_text(_json.dumps(stale), encoding="utf-8")
    assert client.get("/api/company/status").json()["stalled"] is True


def test_company_property_select_for_ad(client: TestClient, migrated_engine) -> None:
    """Company properties are selected for marketing through the same audited
    workflow as listings (owner request 2026-08-30): toggle on → appears on
    /selected → toggle off → gone."""
    with Session(migrated_engine) as session:
        prop = _make_prop(
            session,
            name="Select Target Tower",
            name_fingerprint=f"select target {uuid.uuid4().hex[:6]}",
            address_text="1 Ad Street",
        )
        prop_id = prop.company_property_id
        session.commit()
    response = client.post(
        f"/actions/company-select/{prop_id}", data={"next": "/selected"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert "Select Target Tower" in client.get("/selected").text
    client.post(f"/actions/company-select/{prop_id}", follow_redirects=False)
    assert "Select Target Tower" not in client.get("/selected").text


def test_company_detail_page_renders(client: TestClient, migrated_engine) -> None:
    """Company properties get a dedicated detail page mirroring the listing
    detail page (owner request 2026-08-30)."""
    with Session(migrated_engine) as session:
        prop = _make_prop(
            session,
            name="Detail Page Tower",
            name_fingerprint=f"detail page tower {uuid.uuid4().hex[:6]}",
            address_text="9 Detail Street",
            original_url="https://example.com/detail-tower",
        )
        prop.check_status = "CHECKED"
        prop.availability = {
            "available_units": [
                {"layout": "1BR", "monthly_rent_usd": 3400, "availability_text": "Now"}
            ],
            "no_units_stated": False,
            "evidence": "1BR available now",
            "page_property_name": "Detail Tower",
            "laundry_type": "BUILDING_SHARED_LAUNDRY",
            "laundry_evidence": "laundry room on every floor",
            "amenities": ["gym", "roof deck"],
            "fee_status": "NO_FEE",
        }
        prop_id = prop.company_property_id
        session.commit()
    page = client.get(f"/company/{prop_id}")
    assert page.status_code == 200
    assert "Detail Page Tower" in page.text
    assert "$3,400" in page.text
    assert "AVAILABLE UNITS" in page.text
    assert "SOURCE LINKS" in page.text
    assert "COMMUTE ANALYSIS" in page.text
    # Listing-detail parity sections (07 §11).
    assert "CHECK HISTORY" in page.text
    assert "FLOOR PLAN" in page.text
    assert "Building laundry" in page.text
    assert "No fee (page-stated)" in page.text
    assert "gym" in page.text
    missing = client.get(f"/company/{uuid.uuid4()}", follow_redirects=False)
    assert missing.status_code == 303
    assert missing.headers["location"] == "/company"


def test_company_commute_research(db_engine) -> None:
    """Commute research targets company properties too (owner request
    2026-08-30: researched during checks): persists with the company FK,
    caches, and enforces exactly-one-target."""
    from rental_agent.contracts.fakes import FakeLlmExecutor
    from rental_agent.db.models import Destination
    from rental_agent.enrichment.commute.research import (
        TASK_TYPE as COMMUTE_TASK,
    )
    from rental_agent.enrichment.commute.research import (
        CommuteResearchService,
    )
    from rental_agent.ui import queries

    output = {
        "duration_min_s": 1500,
        "duration_max_s": 2400,
        "likely_routes": ["7"],
        "transfer_count": 0,
        "named_stations": ["Court Sq"],
        "summary": "Roughly 25-40 minutes via the 7.",
        "sources": [{"url": "https://example.test/guide", "title": "Guide"}],
        "confidence": "MEDIUM",
    }
    with Session(db_engine) as session:
        dest = Destination(
            destination_code=f"CO_{uuid.uuid4().hex[:6]}",
            destination_type="UNIVERSITY_CAMPUS",
            display_name="Company Campus",
            routing_anchor_name="Main hall",
            routing_anchor_point="SRID=4326;POINT(-73.99 40.73)",
            registry_version="v1",
        )
        session.add(dest)
        session.flush()
        prop = _make_prop(session, address_text="1 Commute Street")
        service = CommuteResearchService(
            session, FakeLlmExecutor(outputs={COMMUTE_TASK: output}), cache_days=14
        )
        result = service.research(
            company_property_id=prop.company_property_id,
            destination_id=dest.destination_id,
            origin_description="1 Commute Street, Long Island City",
            input_location_hash="company:test",
        )
        assert result.company_property_id == prop.company_property_id
        assert result.canonical_listing_id is None
        again = service.research(
            company_property_id=prop.company_property_id,
            destination_id=dest.destination_id,
            origin_description="1 Commute Street, Long Island City",
            input_location_hash="company:test",
        )
        assert again.commute_result_id == result.commute_result_id  # 14-day cache
        with pytest.raises(ValueError):
            service.research(
                destination_id=dest.destination_id,
                origin_description="x",
                input_location_hash="y",
            )
        cards = queries.commutes_for_company(session, prop.company_property_id)
        assert len(cards) == 1
        assert cards[0]["destination"] == "Company Campus"
        session.rollback()


def test_routed_walking_attaches_to_company_property(db_session, seeded_source) -> None:
    """04 §12 conformance: company walking minutes come from the pedestrian
    router; an implausible route never becomes a walking claim, and
    straight-line stays meters-only."""
    from rental_agent.db.models import TransitStop
    from rental_agent.enrichment.company.service import attach_nearby_transit

    stop = TransitStop(
        provider_source_id=seeded_source,
        provider_stop_id=f"cw{uuid.uuid4().hex[:6]}",
        operator_code="MTA",
        stop_name="Company Sq",
        mode="SUBWAY",
        location_point="SRID=4326;POINT(-73.949 40.746)",
        active_status="ACTIVE",
        dataset_version="t1",
    )
    db_session.add(stop)
    db_session.flush()

    class _Router:
        def walk_route(self, olon, olat, dlon, dlat):  # noqa: ANN001, ANN201
            return (300, 240)  # 300 m in 4 min → plausible 1.25 m/s

    prop = _make_prop(db_session, address_text="1 Transit St")
    prop.latitude, prop.longitude = 40.7466, -73.9485
    prop.availability = {"available_units": []}
    assert attach_nearby_transit(db_session, prop, _Router(), pace_seconds=0) == 1
    entry = prop.availability["nearby_transit"][0]
    assert entry["stop"] == "Company Sq"
    assert entry["walk_min"] == 4
    assert entry["walking_m"] == 300

    class _ImplausibleRouter:
        def walk_route(self, olon, olat, dlon, dlat):  # noqa: ANN001, ANN201
            return (3000, 60)  # 50 m/s — rejected

    prop2 = _make_prop(
        db_session,
        name="Transit Two",
        name_fingerprint=f"transit two {uuid.uuid4().hex[:6]}",
        address_text="2 Transit St",
    )
    prop2.latitude, prop2.longitude = 40.7466, -73.9485
    prop2.availability = {"available_units": []}
    assert attach_nearby_transit(db_session, prop2, _ImplausibleRouter(), pace_seconds=0) == 0
    assert prop2.availability["nearby_transit"][0]["walk_min"] is None


def test_commutes_pick_nearest_destination_of_each_type(db_session) -> None:
    """Owner 2026-08-30: destinations are picked automatically — the nearest
    school AND the nearest major destination by PostGIS distance (like the
    transit panel) — for every geocoded property, units or not."""
    from rental_agent.contracts.fakes import FakeLlmExecutor
    from rental_agent.db.models import CommuteResult, Destination
    from rental_agent.enrichment.commute.research import TASK_TYPE as COMMUTE_TASK
    from rental_agent.jobs.company_refresh import _research_company_commutes

    def _dest(code: str, dtype: str, lon: float) -> Destination:
        dest = Destination(
            destination_code=f"{code}_{uuid.uuid4().hex[:6]}",
            destination_type=dtype,
            display_name=code,
            routing_anchor_name="anchor",
            routing_anchor_point=f"SRID=4326;POINT({lon} 40.75)",
            registry_version="v1",
        )
        db_session.add(dest)
        return dest

    near_school = _dest("NearSchool", "UNIVERSITY_CAMPUS", -73.95)
    _dest("FarSchool", "UNIVERSITY_CAMPUS", -73.80)
    near_major = _dest("NearMajor", "MAJOR_DESTINATION", -73.955)
    _dest("FarMajor", "MAJOR_DESTINATION", -73.75)
    db_session.flush()
    prop = _make_prop(db_session, address_text="1 Auto Commute St")
    prop.latitude, prop.longitude = 40.75, -73.949
    prop.availability = {"available_units": []}  # no units — still researched
    llm = FakeLlmExecutor(
        outputs={
            COMMUTE_TASK: {
                "duration_min_s": 900,
                "duration_max_s": 1500,
                "likely_routes": ["7"],
                "transfer_count": 0,
                "named_stations": [],
                "summary": "short",
                "sources": [{"url": "https://example.test/s"}],
                "confidence": "MEDIUM",
            }
        }
    )
    assert _research_company_commutes(db_session, llm, prop, 14) == 2
    researched = {
        db_session.get(Destination, row.destination_id).display_name
        for row in db_session.execute(
            select(CommuteResult).where(
                CommuteResult.company_property_id == prop.company_property_id
            )
        ).scalars()
    }
    assert researched == {near_school.display_name, near_major.display_name}


def test_amenity_research_fills_gaps_with_sources(db_session, seeded_listing) -> None:
    """Owner 2026-08-30: amenity info for ALL properties. Web research must
    cite sources, never overwrite page-stated values, and flow through the
    normal fact pipeline for listings."""
    from rental_agent.contracts.fakes import FakeLlmExecutor
    from rental_agent.enrichment.amenities.research import (
        TASK_TYPE as AMENITY_TASK,
    )
    from rental_agent.enrichment.amenities.research import (
        AmenityResearchService,
    )
    from rental_agent.ui import queries

    good = {
        "amenities": ["gym", "roof deck"],
        "laundry_type": "BUILDING_SHARED_LAUNDRY",
        "fee_status": "NO_FEE",
        "sources": ["https://example.test/building"],
        "summary": "",
    }
    service = AmenityResearchService(
        db_session, FakeLlmExecutor(outputs={AMENITY_TASK: good})
    )
    output = service.research(name="Test Tower", address="1 Amenity St")
    assert output is not None and output.amenities == ["gym", "roof deck"]
    # No sources → refused outright (04 §19A posture).
    no_sources = AmenityResearchService(
        db_session, FakeLlmExecutor(outputs={AMENITY_TASK: {**good, "sources": []}})
    )
    assert no_sources.research(name="Test Tower", address="1 Amenity St") is None
    # Company merge fills gaps but never overwrites page-stated laundry.
    prop = _make_prop(db_session, address_text="9 Amenity St")
    prop.availability = {
        "available_units": [],
        "laundry_type": "IN_UNIT_WASHER_DRYER_CONFIRMED",
        "laundry_evidence": "in-unit washer/dryer",
    }
    service.apply_to_company(prop, output)
    assert prop.availability["amenities"] == ["gym", "roof deck"]
    assert prop.availability["amenities_sources"] == ["https://example.test/building"]
    assert prop.availability["laundry_type"] == "IN_UNIT_WASHER_DRYER_CONFIRMED"
    assert prop.availability["fee_status"] == "NO_FEE"
    # Listings get a normal amenities fact (chips/Studio pick it up).
    service.record_listing_fact(seeded_listing, output)
    facts = queries.fact_history(db_session, seeded_listing)
    assert any(a["current"] for a in facts.get("amenities", []))


def test_selection_requires_exactly_one_target(db_engine) -> None:
    from rental_agent.canonical.selection_service import MarketingSelectionService
    from rental_agent.contracts.enums import ActorType, SelectionStatus

    with Session(db_engine) as session:
        with pytest.raises(ValueError):
            MarketingSelectionService(session).set_selection(
                status=SelectionStatus.SELECTED,
                actor="test_operator",
                actor_type=ActorType.HUMAN,
            )
        session.rollback()


def test_studio_offers_selected_company_properties(
    client: TestClient, migrated_engine
) -> None:
    """Selected company properties appear in the Studio dropdown and the
    generator accepts the company:<id> target (owner report 2026-08-30)."""
    with Session(migrated_engine) as session:
        prop = _make_prop(
            session,
            name="Studio Tower",
            name_fingerprint=f"studio tower {uuid.uuid4().hex[:6]}",
            address_text="1 Studio Street",
            locality="Long Island City",
        )
        prop.check_status = "CHECKED"
        prop.availability = {
            "available_units": [
                {"layout": "1BR", "monthly_rent_usd": 3200, "availability_text": "Sep 1"}
            ],
            "evidence": "1BR $3,200 available Sep 1",
        }
        prop_id = prop.company_property_id
        session.commit()
    client.post(f"/actions/company-select/{prop_id}", follow_redirects=False)
    page = client.get("/studio").text
    assert "★ Studio Tower" in page
    assert f"company:{prop_id}" in page
    # The generator accepts the company target (local model offline in tests
    # → renders the graceful error card, still HTTP 200).
    response = client.post(
        "/actions/generate-post", data={"listing_id": f"company:{prop_id}"}
    )
    assert response.status_code == 200
    assert "Studio Tower" in response.text
    client.post(f"/actions/company-select/{prop_id}", follow_redirects=False)  # cleanup


def test_llm_config_rejects_bad_base_url(client: TestClient) -> None:
    response = client.post(
        "/actions/llm-config", data={"base_url": "not-a-url"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert "error=" in response.headers["location"]
