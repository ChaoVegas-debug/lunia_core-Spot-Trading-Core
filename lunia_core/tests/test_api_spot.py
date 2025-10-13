import json

import pytest

pytest.importorskip("flask", reason="Flask not available in offline/proxy env")

from app.services.api.flask_app import app


@pytest.mark.requires_flask
def test_spot_strategy_and_risk_endpoints():
    client = app.test_client()
    resp = client.get("/spot/strategies")
    assert resp.status_code == 200
    update = client.post(
        "/spot/strategies",
        data=json.dumps({"weights": {"micro_trend_scalper": 0.6}}),
        content_type="application/json",
    )
    assert update.status_code == 200
    risk_resp = client.post(
        "/spot/risk",
        data=json.dumps({"max_positions": 6}),
        content_type="application/json",
    )
    assert risk_resp.status_code == 200
    backtest = client.post(
        "/spot/backtest",
        data=json.dumps({"strategy": "scalping_breakout", "symbol": "BTCUSDT", "days": 3}),
        content_type="application/json",
    )
    assert backtest.status_code == 200
    payload = backtest.get_json()
    assert payload["strategy"] == "scalping_breakout"
    assert "trades" in payload
