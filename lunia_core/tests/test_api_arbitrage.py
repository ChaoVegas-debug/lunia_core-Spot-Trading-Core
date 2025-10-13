import importlib

import pytest

pytest.importorskip("flask", reason="Flask not available in offline/proxy env")
pytestmark = pytest.mark.requires_flask


def _get_client(monkeypatch):
    monkeypatch.setenv("ENABLE_REDIS", "false")
    from app.services.api import flask_app

    importlib.reload(flask_app)
    return flask_app.app.test_client()


def test_arbitrage_scan_endpoint(monkeypatch):
    client = _get_client(monkeypatch)
    response = client.post("/arbitrage/scan")
    assert response.status_code == 200
    payload = response.get_json()
    assert "opportunities" in payload
    assert isinstance(payload["opportunities"], list)


def test_arbitrage_exec_requires_id(monkeypatch):
    client = _get_client(monkeypatch)
    response = client.post("/arbitrage/exec", json={})
    assert response.status_code == 500


def test_arbitrage_filters_roundtrip(monkeypatch):
    client = _get_client(monkeypatch)
    response = client.post(
        "/arbitrage/filters",
        json={"min_net_roi_pct": 1.5, "sort_dir": "asc"},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["min_net_roi_pct"] == 1.5
    assert payload["sort_dir"] == "asc"

    response = client.get("/arbitrage/filters")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["min_net_roi_pct"] == 1.5
    assert payload["sort_dir"] == "asc"


def test_arbitrage_status(monkeypatch):
    client = _get_client(monkeypatch)
    response = client.get("/arbitrage/status")
    assert response.status_code == 200
    payload = response.get_json()
    assert "total_scans" in payload
    assert "last_opportunities" in payload
