"""
PHASE 14A — EXECUTION GATEWAY: Public API

The Execution Airlock (read-only governance checkpoint).
"""

from .models import (
    RiskLimits,
    ExecutionContextSnapshot,
    ExecutionRequest,
    ExecutionDecision,
    KillSwitchState,
    AuditPayload,
)
from .airlock import ExecutionGateway

__all__ = [
    "ExecutionGateway",
    "RiskLimits",
    "ExecutionContextSnapshot",
    "ExecutionRequest",
    "ExecutionDecision",
    "KillSwitchState",
    "AuditPayload",
]
