"""Phase 4 API Wiring Tests

Comprehensive test suite for risk status, emergency, and structured errors.
"""
import pytest
import json
from decimal import Decimal
from unittest.mock import Mock, patch
from flask import Flask

from forensic.risk.ledger import RiskLedger, RiskState
from forensic.api.risk_routes import risk_bp, set_risk_ledger
from forensic.api.emergency_routes import emergency_bp, EMERGENCY_TOKEN
from forensic.api.serialization import to_json_safe, assert_no_floats
from forensic.api.errors import RiskBlockError


@pytest.fixture
def app():
    """Flask test app."""
    test_app = Flask(__name__)
    test_app.register_blueprint(risk_bp, url_prefix="/api/risk")
    test_app.register_blueprint(emergency_bp, url_prefix="/api/emergency")
    return test_app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


def test_t1_risk_status_json_shape(client):
    """T1: Risk status route exists and returns stable JSON shape."""
    # Initialize ledger
    ledger = RiskLedger()
    ledger.initialize("test-run-1", Decimal("10000"))
    set_risk_ledger(ledger)
    
    response = client.get("/api/risk/status")
    
    assert response.status_code == 200
    data = response.get_json()
    
    # Validate required keys
    assert "meta" in data
    assert "health" in data
    assert "equity" in data
    assert "drawdown" in data
    
    # Check equity fields are strings
    assert isinstance(data["equity"]["current"], str)
    assert isinstance(data["equity"]["hwm"], str)
    assert isinstance(data["equity"]["projected"], str)
    
    # Check drawdown fields are strings
    assert isinstance(data["drawdown"]["current_pct"], str)
    assert isinstance(data["drawdown"]["limit_pct"], str)


def test_t2_freshness_staleness_semantics(client):
    """T2: Freshness indicators work correctly."""
    import time
    
    # Initialize ledger
    ledger = RiskLedger()
    ledger.initialize("test-fresh-1", Decimal("10000"))
    set_risk_ledger(ledger)
    
    base_state = ledger.get_state()
    
    # Case 1: No decisions yet -> is_stale=True, age_seconds=None
    response = client.get("/api/risk/status")
    data = response.get_json()
    
    assert data["meta"]["freshness"]["is_stale"] is True
    assert data["meta"]["freshness"]["age_seconds"] is None
    
    # Case 2: Recent decision (30s ago) -> is_stale=False
    recent_state = RiskState(
        run_id=base_state.run_id,
        timestamp=base_state.timestamp,
        last_trade_id=base_state.last_trade_id,
        equity_high_water_mark=base_state.equity_high_water_mark,
        current_equity=base_state.current_equity,
        current_drawdown_pct=base_state.current_drawdown_pct,
        status=base_state.status,
        active_violation=base_state.active_violation,
        trades_since_peak=base_state.trades_since_peak,
        last_update_ts=time.time() - 30,  # 30 seconds ago
        last_decision_id="recent-decision",
        last_decision_blocked=False,
        last_decision_reason=None
    )
    
    with patch.object(ledger, 'get_state', return_value=recent_state):
        response = client.get("/api/risk/status")
        data = response.get_json()
        
        assert data["meta"]["freshness"]["is_stale"] is False
        age = data["meta"]["freshness"]["age_seconds"]
        assert age is not None
        assert 25 < age < 35  # Tolerant range
    
    # Case 3: Stale decision (400s ago) -> is_stale=True
    stale_state = RiskState(
        run_id=base_state.run_id,
        timestamp=base_state.timestamp,
        last_trade_id=base_state.last_trade_id,
        equity_high_water_mark=base_state.equity_high_water_mark,
        current_equity=base_state.current_equity,
        current_drawdown_pct=base_state.current_drawdown_pct,
        status=base_state.status,
        active_violation=base_state.active_violation,
        trades_since_peak=base_state.trades_since_peak,
        last_update_ts=time.time() - 400,  # 400 seconds ago
        last_decision_id="stale-decision",
        last_decision_blocked=False,
        last_decision_reason=None
    )
    
    with patch.object(ledger, 'get_state', return_value=stale_state):
        response = client.get("/api/risk/status")
        data = response.get_json()
        
        assert data["meta"]["freshness"]["is_stale"] is True
        assert data["meta"]["freshness"]["age_seconds"] > 300
    
    # Case 4: Future skew (clock skew) -> is_stale=True, negative age, no crash
    future_state = RiskState(
        run_id=base_state.run_id,
        timestamp=base_state.timestamp,
        last_trade_id=base_state.last_trade_id,
        equity_high_water_mark=base_state.equity_high_water_mark,
        current_equity=base_state.current_equity,
        current_drawdown_pct=base_state.current_drawdown_pct,
        status=base_state.status,
        active_violation=base_state.active_violation,
        trades_since_peak=base_state.trades_since_peak,
        last_update_ts=time.time() + 3600,  # 1 hour in future
        last_decision_id="future-decision",
        last_decision_blocked=False,
        last_decision_reason=None
    )
    
    with patch.object(ledger, 'get_state', return_value=future_state):
        response = client.get("/api/risk/status")
        data = response.get_json()
        
        # Should not crash
        assert response.status_code == 200
        assert data["meta"]["freshness"]["is_stale"] is True  # Future = stale
        assert data["meta"]["freshness"]["age_seconds"] < 0  # Negative age


def test_t3_risk_block_feedback():
    """T3: RiskBlockError generates proper HTTP 422 payload."""
    error = RiskBlockError(
        reason="CURRENT_DRAWDOWN_25PCT",
        decision_id="test-decision-123",
        mode="ENFORCE",
        current_dd=Decimal("0.26"),
        projected_dd=Decimal("0.28"),
        limit=Decimal("0.25"),
        health_status="CRITICAL"
    )
    
    payload = error.to_payload()
    
    # Validate structure
    assert payload["status"] == "error"
    assert payload["error_code"] == "RISK_BLOCK"
    assert payload["details"]["reason"] == "CURRENT_DRAWDOWN_25PCT"
    assert payload["details"]["decision_id"] == "test-decision-123"
    
    # Validate Decimal-as-string
    assert isinstance(payload["details"]["current_dd"], str)
    assert isinstance(payload["details"]["projected_dd"], str)
    assert isinstance(payload["details"]["limit"], str)
    
    assert payload["details"]["current_dd"] == "0.26"
    assert payload["details"]["limit"] == "0.25"


def test_t4_emergency_endpoint_security(client):
    """T4: Emergency endpoint security (fail-closed)."""
    # Case 1: No headers -> 403
    response = client.post("/api/emergency/liquidate")
    assert response.status_code == 403
    data = response.get_json()
    assert data["error_code"] == "INVALID_EMERGENCY_TOKEN"
    
    # Case 2: Wrong token -> 403
    response = client.post("/api/emergency/liquidate", headers={
        "X-EMERGENCY-TOKEN": "WRONG_TOKEN",
        "X-EMERGENCY-ACK": "I_UNDERSTAND"
    })
    assert response.status_code == 403
    
    # Case 3: Missing ACK -> 403
    response = client.post("/api/emergency/liquidate", headers={
        "X-EMERGENCY-TOKEN": EMERGENCY_TOKEN
    })
    assert response.status_code == 403
    assert response.get_json()["error_code"] == "INVALID_EMERGENCY_HEADERS"
    
    # Case 4: Wrong ACK value -> 403
    response = client.post("/api/emergency/liquidate", headers={
        "X-EMERGENCY-TOKEN": EMERGENCY_TOKEN,
        "X-EMERGENCY-ACK": "WRONG_ACK"
    })
    assert response.status_code == 403


def test_t5_emergency_liquidation_success(client):
    """T5: Emergency liquidation success path."""
    response = client.post("/api/emergency/liquidate", headers={
        "X-EMERGENCY-TOKEN": EMERGENCY_TOKEN,
        "X-EMERGENCY-ACK": "I_UNDERSTAND"
    })
    
    assert response.status_code == 200
    data = response.get_json()
    
    assert data["status"] == "ok"
    assert data["action"] == "EMERGENCY_LIQUIDATION"
    assert "intent_id" in data
    assert "decision_id" in data
    assert "details" in data
    
    # Validate normalized qty is string
    assert isinstance(data["details"]["normalized_qty"], str)
    assert isinstance(data["details"]["step_size"], str)
    assert isinstance(data["details"]["truncation_loss"], str)


def test_t6_float_leak_detector():
    """T6: Assert no floats in risk payloads."""
    # Test Decimal-as-string conversion
    obj = {
        "equity": {
            "current": Decimal("10000.50"),
            "hwm": Decimal("10500.00")
        },
        "drawdown": {
            "current_pct": Decimal("0.047619"),
            "limit": Decimal("0.25")
        },
        "age_seconds": 12.5  # Float allowed for metadata
    }
    
    safe_obj = to_json_safe(obj)
    
    # Assert Decimals converted to strings
    assert isinstance(safe_obj["equity"]["current"], str)
    assert isinstance(safe_obj["equity"]["hwm"], str)
    assert isinstance(safe_obj["drawdown"]["current_pct"], str)
    
    # Float leak detection
    with pytest.raises(RuntimeError, match="Float detected"):
        bad_obj = {
            "equity": {
                "current": 10000.50  # FLOAT (bad)
            }
        }
        assert_no_floats(bad_obj, "test_payload")


def test_t7_regression_guard():
    """T7: Regression guard - Phase 0-3 remain GREEN."""
    import subprocess
    
    # Phase 0
    result_p0 = subprocess.run(
        ["python3", "-m", "pytest",
         "tests/forensic/test_primary_autopsy_10k_to_1k.py", "-q"],
        cwd="/Users/neomind/alladin/lunia_core-Spot-Trading-Core/lunia_core",
        capture_output=True, text=True
    )
    assert result_p0.returncode == 0, f"Phase 0 regression: {result_p0.stdout}"
    
    # Phase 1 & 2 & 3
    result_p123 = subprocess.run(
        ["python3", "-m", "pytest",
         "tests/forensic/risk/", "-q"],
        cwd="/Users/neomind/alladin/lunia_core-Spot-Trading-Core/lunia_core",
        capture_output=True, text=True
    )
    assert result_p123.returncode == 0, f"Phase 1/2/3 regression: {result_p123.stdout}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
