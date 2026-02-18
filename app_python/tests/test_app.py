import socket as socket_module
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app import app


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


def test_get_root_ok_and_structure(client: TestClient):
    r = client.get("/")
    assert r.status_code == 200  # noqa: PLR2004

    data = r.json()
    for key in ("service", "system", "runtime", "request", "endpoints"):
        assert key in data

    assert data["service"]["framework"] == "FastAPI"
    assert isinstance(data["service"]["name"], str)
    assert isinstance(data["service"]["version"], str)

    assert isinstance(data["system"]["hostname"], str)
    assert isinstance(data["system"]["platform"], str)
    assert isinstance(data["system"]["python_version"], str)

    assert isinstance(data["runtime"]["uptime_seconds"], int)
    assert data["runtime"]["uptime_seconds"] >= 0
    assert isinstance(data["runtime"]["uptime_human"], str)

    # ISO-ish check (implicit assert no ValueError raised)
    datetime.fromisoformat(data["runtime"]["current_time"])

    assert data["runtime"]["timezone"] == "UTC"

    assert data["request"]["method"] == "GET"
    assert data["request"]["path"] == "/"
    assert isinstance(data["request"]["user_agent"], str)


def test_root_endpoints_list_contains_our_routes(client: TestClient):
    r = client.get("/")
    data = r.json()

    endpoints = data["endpoints"]
    assert isinstance(endpoints, list)
    assert all(isinstance(e, dict) for e in endpoints)

    # Ensure HEAD/OPTIONS were filtered out
    methods = {e["method"] for e in endpoints}
    assert "HEAD" not in methods
    assert "OPTIONS" not in methods

    # Ensure our routes show up
    pairs = {(e["path"], e["method"]) for e in endpoints}
    assert ("/", "GET") in pairs
    assert ("/health", "GET") in pairs


def test_get_health_ok(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200  # noqa: PLR2004

    data = r.json()
    assert data["status"] == "healthy"
    assert isinstance(data["uptime_seconds"], int)
    assert data["uptime_seconds"] >= 0
    datetime.fromisoformat(data["timestamp"])


def test_404_is_returned_for_unknown_path(client: TestClient):
    r = client.get("/does-not-exist")
    assert r.status_code == 404  # noqa: PLR2004
    # FastAPI default shape
    assert "detail" in r.json()


def test_method_not_allowed(client: TestClient):
    r = client.post("/health")
    assert r.status_code == 405  # noqa: PLR2004


def test_internal_error_handler_returns_json(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    # Force an exception inside GET /

    def boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(socket_module, "gethostname", boom)

    r = client.get("/")
    assert r.status_code == 500  # noqa: PLR2004

    data = r.json()
    assert data["error"] == "Internal Server Error"
    assert "message" in data
    assert "boom" in data["message"]
