import importlib

import pytest


pytest.importorskip("flask", reason="Flask not available in offline/proxy env")
pytestmark = pytest.mark.requires_flask


def test_ai_run_endpoint(monkeypatch):
    monkeypatch.setenv("BINANCE_USE_TESTNET", "false")
    monkeypatch.setenv("ENABLE_REDIS", "false")
    from app.services.api import flask_app

    importlib.reload(flask_app)
    client = flask_app.app.test_client()
    response = client.post("/ai/run")

    assert response.status_code == 200
    data = response.get_json()
    assert "executed" in data
    assert "errors" in data
