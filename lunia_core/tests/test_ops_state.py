import os

import pytest

pytest.importorskip("flask", reason="Flask not available in offline/proxy env")

from app.core.state import reset_state
from app.services.api.flask_app import app


@pytest.fixture(autouse=True)
def _reset_state():
    reset_state()
    yield
    reset_state()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr("app.services.api.flask_app.OPS_TOKEN", None, raising=False)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_ops_state_get(client):
    resp = client.get("/ops/state")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["auto_mode"] in {True, False}


def test_ops_state_toggle_requires_token(monkeypatch, client):
    monkeypatch.setattr("app.services.api.flask_app.OPS_TOKEN", "secret", raising=False)
    resp = client.post("/ops/auto_off")
    assert resp.status_code == 403
    monkeypatch.setattr("app.services.api.flask_app.OPS_TOKEN", None, raising=False)
    resp = client.post("/ops/auto_off")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["auto_mode"] is False
