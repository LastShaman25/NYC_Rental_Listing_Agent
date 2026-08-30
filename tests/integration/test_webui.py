"""Smoke tests for the Stitch web UI (FastAPI): pages render, actions persist."""

import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from tests.conftest import requires_db

from rental_agent.webui.app import create_app

pytestmark = [pytest.mark.integration, requires_db]


@pytest.fixture()
def client(migrated_engine) -> TestClient:
    factory = sessionmaker(bind=migrated_engine, expire_on_commit=False)
    settings = SimpleNamespace(operator_id="test_operator")
    app = create_app(factory=factory, settings=settings)
    return TestClient(app)


def test_pages_render(client: TestClient) -> None:
    for path in ("/", "/inventory", "/clients", "/selected", "/studio", "/settings"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert "RentAgent" in response.text, path


def test_old_pages_redirect_to_settings(client: TestClient) -> None:
    for path, target in (
        ("/review", "/settings?section=review"),
        ("/operations", "/settings?section=logs"),
    ):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 303, path
        assert response.headers["location"] == target, path


def test_settings_sections_show_one_topic_at_a_time(client: TestClient) -> None:
    """Apple-settings style (owner request 2026-08-29): ?section= picks the
    topic; other topics stay off the page."""
    default = client.get("/settings").text
    assert "Full re-acquisition" in default
    assert "BASE URL (OPTIONAL)" not in default
    llm = client.get("/settings", params={"section": "llm"}).text
    assert "BASE URL (OPTIONAL)" in llm
    assert "Full re-acquisition" not in llm
    review = client.get("/settings", params={"section": "review"}).text
    assert "DUPLICATE CANDIDATES" in review
    logs = client.get("/settings", params={"section": "logs"}).text
    assert "REFRESH RUNS" in logs


def test_inventory_filters_roundtrip(client: TestClient) -> None:
    response = client.get(
        "/inventory",
        params={"layout": ["STUDIO"], "min_rent": "1000", "max_rent": "4000", "in_unit": "1"},
    )
    assert response.status_code == 200
    assert "UNITS" in response.text


def test_unknown_listing_detail_redirects(client: TestClient) -> None:
    response = client.get(f"/listing/{uuid.uuid4()}", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/inventory"


def test_create_preset_persists(client: TestClient) -> None:
    label = f"webui-test-{uuid.uuid4().hex[:6]}"
    response = client.post("/actions/preset", data={"label": label}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/clients"
    assert label in client.get("/clients").text


def test_duplicate_client_name_is_a_friendly_error(client: TestClient) -> None:
    """A duplicate pseudonym used to escape as a 500 (owner report
    2026-08-30); it must redirect with a readable message instead."""
    label = f"dup-{uuid.uuid4().hex[:6]}"
    client.post("/actions/preset", data={"label": label}, follow_redirects=False)
    for attempt in (label, label.upper(), f"  {label}  "):
        response = client.post(
            "/actions/preset", data={"label": attempt}, follow_redirects=False
        )
        assert response.status_code == 303, attempt
        assert "error=" in response.headers["location"], attempt
    blank = client.post("/actions/preset", data={"label": "   "}, follow_redirects=False)
    assert "error=" in blank.headers["location"]


def test_readding_removed_client_restores_it(client: TestClient, migrated_engine) -> None:
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from rental_agent.db.models import ClientSearchPreset

    label = f"restore-{uuid.uuid4().hex[:6]}"
    client.post("/actions/preset", data={"label": label}, follow_redirects=False)
    with Session(migrated_engine) as session:
        preset = session.execute(
            select(ClientSearchPreset).where(ClientSearchPreset.label == label)
        ).scalar_one()
        preset_id = preset.client_search_preset_id
    client.post(f"/actions/archive-client/{preset_id}", follow_redirects=False)
    response = client.post("/actions/preset", data={"label": label}, follow_redirects=False)
    assert response.status_code == 303
    assert "started=Restored" in response.headers["location"]
    with Session(migrated_engine) as session:
        restored = session.get(ClientSearchPreset, preset_id)
        assert restored is not None and restored.archived_at is None


def test_healthz(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}
