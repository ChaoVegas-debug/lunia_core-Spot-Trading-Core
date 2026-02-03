"""
EXECUTION MONITORING — Public API

PHASE 14D: Post-Trade Observer & Reconciliation

⚠️ CRITICAL GOVERNANCE:
ExecutionMonitor is a READ-ONLY observer.

Responsibilities:
- Resolve UNKNOWN order statuses
- Track order lifecycle
- Emit audit trail

NOT responsible for:
- Trading decisions (Hands Not Brain)
- Order creation/cancellation
- Autonomous execution

Import Rules:
Monitor MUST ONLY be imported by:
- Application layer / orchestration
- Tests

NEVER import in:
- shadow_mode
- genome_dsl
- virtual_portfolio
- hud_api
- execution_gateway (Phase 14A)
- execution_router (Phase 14C)

Violation = bypass risk or circular dependency.
"""

from .monitor import ExecutionMonitor
from .models import (
    ReconciliationResult,
    ReconciliationStatus,
    MonitorStatus,
    stable_json,
    canonical_ts,
)

__all__ = [
    "ExecutionMonitor",
    "ReconciliationResult",
    "ReconciliationStatus",
    "MonitorStatus",
    "stable_json",
    "canonical_ts",
]
