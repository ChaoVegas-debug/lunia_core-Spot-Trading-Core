"""Emergency Liquidation Blueprint (PHASE 4)

Simulation-only panic button endpoint.
Requires strict header validation, routes through Phase 3 Liquidator.
"""
from decimal import Decimal
from typing import Dict, Any
from flask import Blueprint, request, jsonify, Response

from forensic.execution.liquidator import Liquidator
from forensic.api.errors import EmergencyError
from forensic.api.serialization import to_json_safe


# Emergency token (simulation constant)
EMERGENCY_TOKEN = "SIMULATION_EMERGENCY_TOKEN_PHASE4"


# Blueprint
emergency_bp = Blueprint("emergency_bp", __name__)


@emergency_bp.post("/liquidate")
def emergency_liquidate() -> Response:
    """POST /api/emergency/liquidate - Panic button (simulation only).
    
    Requires headers:
    - X-EMERGENCY-TOKEN: {EMERGENCY_TOKEN}
    - X-EMERGENCY-ACK: I_UNDERSTAND
    
    Returns:
        JSON with liquidation details or error
    """
    # Validate headers (fail-closed)
    token = request.headers.get("X-EMERGENCY-TOKEN")
    ack = request.headers.get("X-EMERGENCY-ACK")
    
    if not token or token != EMERGENCY_TOKEN:
        print(f"[RISK_VIOLATION] INVALID_EMERGENCY_TOKEN")
        error = EmergencyError("INVALID_EMERGENCY_TOKEN", "Emergency endpoint requires valid token")
        return jsonify(error.to_payload()), 403
    
    if not ack or ack != "I_UNDERSTAND":
        print(f"[RISK_VIOLATION] INVALID_EMERGENCY_HEADERS missing_ack={ack}")
        error = EmergencyError("INVALID_EMERGENCY_HEADERS", "Emergency endpoint requires ACK header")
        return jsonify(error.to_payload()), 403
    
    # Get portfolio snapshot (mock for Phase 4 - should read from actual portfolio)
    # For now, return mock response showing the contract
    try:
        portfolio_snapshot = {"position_qty": Decimal("0.1")}  # Mock
        
        # Generate emergency intent via Phase 3 Liquidator
        intent = Liquidator.generate_emergency_liquidation(portfolio_snapshot)
        
        print(f"[EMERGENCY_REQUEST_RECEIVED] intent_id={intent['id']}")
        
        # Phase 4: Mock execution (full integration would call harness here)
        # For Phase 4 API wiring, we return success with normalization proof
        
        payload = {
            "status": "ok",
            "action": "EMERGENCY_LIQUIDATION",
            "intent_id": intent["id"],
            "decision_id": "emergency-mock-decision",  # Would come from actual execution
            "details": {
                "symbol": "BTC/USDT",
                "raw_position": intent["metadata"]["raw_qty"],
                "normalized_qty": str(intent["qty"]),
                "step_size": intent["metadata"]["step_size"],
                "truncation_loss": intent["metadata"]["truncation_loss"],
                "emergency_reason": intent["emergency_reason"]
            }
        }
        
        print(f"[EMERGENCY_EXECUTION_COMPLETE] intent_id={intent['id']} qty={intent['qty']}")
        
        safe_payload = to_json_safe(payload)
        return jsonify(safe_payload), 200
        
    except ValueError as e:
        # Liquidator errors (no position, too small, etc.)
        if "No position" in str(e):
            error = EmergencyError("NO_POSITION_TO_LIQUIDATE", str(e))
        elif "too small" in str(e):
            error = EmergencyError("POSITION_TOO_SMALL_FOR_STEPSIZE", str(e))
        else:
            error = EmergencyError("ARCHITECTURAL_VIOLATION", str(e))
        
        return jsonify(error.to_payload()), 400
