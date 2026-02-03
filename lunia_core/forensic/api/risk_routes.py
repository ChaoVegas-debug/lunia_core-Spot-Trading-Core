"""Risk Status Blueprint (PHASE 4)

Read-only risk observability endpoint.
Exposes RiskLedger state via stable JSON API.
"""
import time
from decimal import Decimal
from typing import Optional, Dict, Any
from flask import Blueprint, jsonify, Response

from forensic.risk.ledger import RiskLedger
from forensic.api.serialization import to_json_safe, assert_no_floats


# Global ledger instance (should be injected in production)
# For Phase 4, we'll use a module-level instance
_ledger_instance: Optional[RiskLedger] = None


def set_risk_ledger(ledger: RiskLedger):
    """Set global ledger instance for API access."""
    global _ledger_instance
    _ledger_instance = ledger


def get_risk_ledger() -> RiskLedger:
    """Get global ledger instance."""
    if _ledger_instance is None:
        raise RuntimeError("Risk ledger not initialized. Call set_risk_ledger() first.")
    return _ledger_instance


# Blueprint
risk_bp = Blueprint("risk_bp", __name__)


@risk_bp.get("/status")
def get_risk_status() -> Response:
    """GET /api/risk/status - Risk observability endpoint.
    
    Returns:
        JSON with health, equity, drawdown, freshness
    """
    try:
        ledger = get_risk_ledger()
        state = ledger.get_state()
    except RuntimeError:
        # Ledger not initialized - return minimal response
        return jsonify({
            "meta": {
                "run_id": None,
                "mode": "UNKNOWN",
                "is_halted": False,
                "freshness": {
                    "age_seconds": None,
                    "is_stale": True,
                    "stale_soft_seconds": 300,
                    "stale_hard_seconds": 3600
                }
            },
            "health": {
                "status": "UNKNOWN",
                "severity": "GRAY",
                "reason": "LEDGER_NOT_INITIALIZED"
            },
            "equity": None,
            "drawdown": None,
            "last_decision": None
        }), 200
    
    # Compute freshness
    if state.last_update_ts is not None:
        age_seconds = time.time() - state.last_update_ts
        # Stale if too old OR if timestamp is in future (clock skew)
        is_stale = age_seconds > 300 or age_seconds < 0  # Phase 4: handle future timestamps
    else:
        age_seconds = None
        is_stale = True
    
    # Health mapping (deterministic)
    health_status, severity, reason = _compute_health(state)
    
    # Build response
    payload = {
        "meta": {
            "run_id": state.run_id,
            "mode": "SHADOW",  # Phase 4: hardcoded for now, should read from config
            "is_halted": state.status == "HALT_OBSERVED",
            "freshness": {
                "age_seconds": age_seconds,
                "is_stale": is_stale,
                "stale_soft_seconds": 300,
                "stale_hard_seconds": 3600
            }
        },
        "health": {
            "status": health_status,
            "severity": severity,
            "reason": reason
        },
        "equity": {
            "current": str(state.current_equity),
            "hwm": str(state.equity_high_water_mark),
            "projected": str(state.current_equity)  # Phase 4: no projection in status endpoint
        },
        "drawdown": {
            "current_pct": str(state.current_drawdown_pct),
            "projected_pct": str(state.current_drawdown_pct),  # Same as current for now
            "warning_pct": "0.200000",
            "limit_pct": "0.250000"
        },
        "last_decision": {
            "decision_id": state.last_decision_id,
            "blocked": state.last_decision_blocked,
            "reason": state.last_decision_reason,
            "age_seconds": age_seconds
        } if state.last_decision_id else None
    }
    
    # Convert Decimals to strings
    safe_payload = to_json_safe(payload)
    
    # Assert no floats in risk/equity/drawdown
    assert_no_floats(safe_payload.get("equity", {}), "equity")
    assert_no_floats(safe_payload.get("drawdown", {}), "drawdown")
    
    return jsonify(safe_payload), 200, {"Cache-Control": "max-age=2"}


def _compute_health(state) -> tuple[str, str, Optional[str]]:
    """Compute health status from ledger state.
    
    Returns:
        (status, severity, reason)
    """
    current_dd = state.current_drawdown_pct
    warning_pct = Decimal("0.20")
    limit_pct = Decimal("0.25")
    
    # HALT takes priority
    if state.status == "HALT_OBSERVED":
        return ("HALT", "RED", "SYSTEM_HALTED")
    
    # Critical if at/above limit
    if current_dd >= limit_pct:
        # In SHADOW mode, this is a warning signal
        return ("WARNING", "YELLOW", "WOULD_BLOCK_IN_ENFORCE")
    
    # Warning if approaching limit
    if current_dd >= warning_pct:
        return ("WARNING", "YELLOW", "APPROACHING_LIMIT")
    
    # Healthy
    return ("HEALTHY", "GREEN", None)
