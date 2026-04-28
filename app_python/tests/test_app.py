import io
import json
import re
import socket as socket_module
from datetime import datetime

import pytest
import structlog
from fastapi.testclient import TestClient

from app import app, configure_logging, settings


class TTYBuffer(io.StringIO):
    def isatty(self) -> bool:
        return True


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
    assert data["service"]["name"] == settings.app_name
    assert data["service"]["version"] == settings.app_version

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


def test_metrics_endpoint_exposes_prometheus_metrics(client: TestClient):
    client.get("/")
    client.get("/health")

    r = client.get("/metrics")
    assert r.status_code == 200  # noqa: PLR2004
    assert r.headers["content-type"].startswith("text/plain")

    metrics = r.text
    assert "# HELP http_requests_total Total number of requests" in metrics
    assert "# TYPE http_requests_total counter" in metrics
    assert 'http_requests_total{handler="/",method="GET",status="2xx"}' in metrics
    assert 'http_requests_total{handler="/health",method="GET",status="2xx"}' in metrics
    assert "# TYPE http_request_duration_seconds histogram" in metrics
    assert "# TYPE http_request_duration_highr_seconds histogram" in metrics
    assert "# TYPE http_requests_in_progress gauge" in metrics
    assert "# TYPE devops_info_endpoint_calls_total counter" in metrics
    assert 'devops_info_endpoint_calls_total{endpoint="/"}' in metrics
    assert 'devops_info_endpoint_calls_total{endpoint="/health"}' in metrics
    assert "# TYPE devops_info_system_collection_seconds histogram" in metrics


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


def test_structlog_console_output_includes_required_fields():
    output = TTYBuffer()
    configure_logging(output)

    try:
        structlog.get_logger("test-logger").info(
            "hello", method="GET", path="/health", status_code=200
        )
        stderr = output.getvalue()
    finally:
        configure_logging()

    stderr = re.sub(r"\x1b\[[0-9;]*m", "", stderr)

    assert "hello" in stderr
    assert "info" in stderr
    assert "test-logger" in stderr
    assert settings.app_name in stderr
    assert "method=GET" in stderr
    assert "path=/health" in stderr
    assert "status_code=200" in stderr


def test_structlog_json_output_includes_required_fields():
    output = io.StringIO()
    configure_logging(output)

    try:
        structlog.get_logger("test-json-logger").info(
            "hello", method="GET", path="/health", status_code=200
        )
        stderr = output.getvalue()
    finally:
        configure_logging()

    data = json.loads(stderr)

    assert data["timestamp"].endswith("Z")
    assert data["level"] == "info"
    assert data["logger"] == "test-json-logger"
    assert data["app_name"] == settings.app_name
    assert data["message"] == "hello"
    assert data["method"] == "GET"
    assert data["path"] == "/health"
    assert data["status_code"] == 200  # noqa: PLR2004
