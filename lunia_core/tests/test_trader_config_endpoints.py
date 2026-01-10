import pytest
import json
from app.services.api.flask_app import app
from app.core.state import reset_state, get_state

@pytest.fixture
def client():
    app.config["TESTING"] = True
    reset_state()
    with app.test_client() as client:
        yield client

def test_spot_mode_lifecycle(client):
    # Test Manual mode switch
    resp = client.post("/spot/mode", json={"mode": "MANUAL"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["mode"] == "MANUAL"
    
    state = get_state()
    assert state["auto_mode"] is False
    assert state["global_stop"] is False

    # Test Auto mode switch
    resp = client.post("/spot/mode", json={"mode": "AUTO"})
    assert resp.status_code == 200
    state = get_state()
    assert state["auto_mode"] is True

    # Test Stop mode switch
    resp = client.post("/spot/mode", json={"mode": "STOP"})
    assert resp.status_code == 200
    state = get_state()
    assert state["global_stop"] is True

def test_exchange_config(client):
    # Initial list
    resp = client.get("/spot/exchanges")
    assert resp.status_code == 200
    exchanges = resp.get_json()
    assert len(exchanges) >= 4
    binance = next(e for e in exchanges if e["id"] == "binance")
    assert binance["enabled"] is True

    # Update config (Disable Binance)
    resp = client.post("/spot/exchanges/binance/config", json={"enabled": False, "allocation": 0.0})
    assert resp.status_code == 200
    
    # Verify persistence
    resp = client.get("/spot/exchanges")
    binance = next(e for e in resp.get_json() if e["id"] == "binance")
    assert binance["enabled"] is False
    assert binance["allocation"] == 0.0

def test_strategies_config(client):
    # Initial enriched list
    resp = client.get("/spot/strategies")
    assert resp.status_code == 200
    strats = resp.get_json()
    assert isinstance(strats, list)
    scalper = next(s for s in strats if s["id"] == "micro_trend_scalper")
    assert "horizon" in scalper
    assert "risk_label" in scalper

    # Update weights (New List Format)
    new_config = [
        {"id": "micro_trend_scalper", "enabled": True, "weight": 0.8},
        {"id": "scalping_breakout", "enabled": False, "weight": 0.0}
    ]
    resp = client.post("/spot/strategies", json=new_config)
    assert resp.status_code == 200
    
    # Verify
    state = get_state()
    weights = state["spot"]["weights"]
    assert weights["micro_trend_scalper"] == 0.8
    assert weights["scalping_breakout"] == 0.0
