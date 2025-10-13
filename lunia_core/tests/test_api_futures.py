import importlib

import pytest

pytest.importorskip("flask", reason="Flask not available in offline/proxy env")
pytestmark = pytest.mark.requires_flask


def test_futures_demo_endpoint(monkeypatch):
    monkeypatch.setenv("BINANCE_FUTURES_TESTNET", "false")
    monkeypatch.setenv("ENABLE_REDIS", "false")
    from app.services.api import flask_app

    importlib.reload(flask_app)
    client = flask_app.app.test_client()
    response = client.post(
        "/trade/futures/demo",
        json={"symbol": "BTCUSDT", "side": "BUY", "qty": 0.001, "leverage": 1},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert "order" in payload
