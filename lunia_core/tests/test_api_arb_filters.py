import importlib

import pytest

pytest.importorskip("flask", reason="Flask not available in offline/proxy env")
pytestmark = pytest.mark.requires_flask


def test_auto_toggle(monkeypatch):
    monkeypatch.setenv("ENABLE_REDIS", "false")
    from app.services.api import flask_app

    importlib.reload(flask_app)
    client = flask_app.app.test_client()

    response = client.post("/arbitrage/auto_on")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["arb"]["auto_mode"] is True

    response = client.post("/arbitrage/auto_off")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["arb"]["auto_mode"] is False
