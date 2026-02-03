"""Structured Error Responses (PHASE 4)

Defines error types for risk blocks and emergency failures.
"""
from typing import Optional, Dict, Any
from decimal import Decimal


class RiskBlockError(Exception):
    """Raised when trade is blocked by risk enforcement.
    
    PHASE 4: Provides structured payload for HTTP 422 response.
    """
    
    def __init__(
        self,
        reason: str,
        decision_id: str,
        mode: str,
        current_dd: Decimal,
        projected_dd: Decimal,
        limit: Decimal,
        health_status: str = "CRITICAL"
    ):
        self.reason = reason
        self.decision_id = decision_id
        self.mode = mode
        self.current_dd = current_dd
        self.projected_dd = projected_dd
        self.limit = limit
        self.health_status = health_status
        
        super().__init__(f"Risk block: {reason}")
    
    def to_payload(self) -> Dict[str, Any]:
        """Generate structured JSON payload.
        
        Returns:
            Dict for HTTP 422 response (Decimal-as-string)
        """
        return {
            "status": "error",
            "error_code": "RISK_BLOCK",
            "message": "Trade rejected by Risk Engine",
            "details": {
                "reason": self.reason,
                "decision_id": self.decision_id,
                "mode": self.mode,
                "current_dd": str(self.current_dd),
                "projected_dd": str(self.projected_dd),
                "limit": str(self.limit),
                "health_status": self.health_status
            }
        }


class EmergencyError(Exception):
    """Base class for emergency endpoint errors."""
    
    def __init__(self, error_code: str, message: str):
        self.error_code = error_code
        self.message = message
        super().__init__(message)
    
    def to_payload(self) -> Dict[str, Any]:
        return {
            "status": "error",
            "error_code": self.error_code,
            "message": self.message
        }
