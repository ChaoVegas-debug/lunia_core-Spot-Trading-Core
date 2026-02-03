"""
EXECUTION ROUTER — Public API

PHASE 14C: The Single Chokepoint (Gateway → Client)

⚠️ CRITICAL GOVERNANCE:
ExecutionRouter is the ONLY legal path from decision (14A) to execution (14B).

Import Rules:
- ExecutionRouter MUST ONLY be imported by:
  - Application layer / orchestration
  - Tests

NEVER import in:
- shadow_mode
- genome_dsl
- virtual_portfolio
- hud_api
- execution_gateway (Phase 14A)
- exchange_connectivity (Phase 14B)

Violation = bypass of the single chokepoint.
"""

from .router import ExecutionRouter
from .models import RoutingResult, RoutingStatus, RoutingError, stable_json, derive_decision_id

__all__ = [
    "ExecutionRouter",
    "RoutingResult",
    "RoutingStatus",
    "RoutingError",
    "stable_json",
    "derive_decision_id",
]
