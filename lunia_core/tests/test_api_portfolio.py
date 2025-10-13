import importlib

import pytest

pytest.importorskip("flask", reason="Flask not available in offline/proxy env")
pytestmark = pytest.mark.requires_flask


def test_portfolio_and_balances(monkeypatch):
    monkeypatch.setenv("BINANCE_USE_TESTNET", "false")
    monkeypatch.setenv("ENABLE_REDIS", "false")
    from app.services.api import flask_app

    importlib.reload(flask_app)
    client = flask_app.app.test_client()

    portfolio_resp = client.get("/portfolio")
    assert portfolio_resp.status_code == 200
    portfolio = portfolio_resp.get_json()
    assert "positions" in portfolio
    assert "equity_usd" in portfolio

    balances_resp = client.get("/balances")
    assert balances_resp.status_code == 200
    balances = balances_resp.get_json()
    assert "balances" in balances
