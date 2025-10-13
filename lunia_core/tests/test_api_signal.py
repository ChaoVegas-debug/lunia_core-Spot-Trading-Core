import importlib

import pytest

pytest.importorskip("flask", reason="Flask not available in offline/proxy env")
pytestmark = pytest.mark.requires_flask


def test_manual_signal(monkeypatch):
    monkeypatch.setenv("BINANCE_USE_TESTNET", "false")
    monkeypatch.setenv("ENABLE_REDIS", "false")
    from app.services.api import flask_app

    importlib.reload(flask_app)
    client = flask_app.app.test_client()
    response = client.post(
        "/signal",
        json={"symbol": "BTCUSDT", "side": "BUY", "qty": 0.01},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert "executed" in data
    assert isinstance(data["executed"], list)
