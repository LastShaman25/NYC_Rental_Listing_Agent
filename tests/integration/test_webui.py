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
    for path in ("/review", "/operations"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 303, path
        assert response.headers["location"] == "/settings", path


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


def test_healthz(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}
