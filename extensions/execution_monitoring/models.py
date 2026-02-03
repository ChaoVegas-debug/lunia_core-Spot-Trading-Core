"""
PHASE 14D — EXECUTION MONITORING: Models

Post-trade reconciliation result contracts.

CRITICAL RULES:
- Read-only observer (no write operations)
- Ambiguity resolution (UNKNOWN → query status)
- Fail-closed (exceptions → UNRESOLVED)
- Deterministic (stable JSON)
- No wall-clock
"""

import json
from dataclasses import dataclass
from typing import Dict, Any, Optional, Literal, List


# ────────────────────────────────────────────────────────────────────────────────
# TYPE ALIASES
# ────────────────────────────────────────────────────────────────────────────────

ReconciliationStatus = Literal[
    "FINAL",        # Definitive terminal state (FILLED, REJECTED, CANCELED)
    "PENDING",      # Active order (NEW, PARTIALLY_FILLED)
    "UNRESOLVED",   # Cannot determine (query failed, missing data)
]

MonitorStatus = Literal[
    "OK",           # Monitoring succeeded
    "DEGRADED",     # Partial success (reconciliation incomplete)
    "ERROR",        # Monitoring failed
]


# ────────────────────────────────────────────────────────────────────────────────
# RECONCILIATION RESULT
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class ReconciliationResult:
    """
    Result of post-trade reconciliation.
    
    Fields:
    - status: ReconciliationStatus (FINAL, PENDING, UNRESOLVED)
    - ts_ms: Canonical deterministic timestamp
    - decision_id: Decision ID from router
    - client_order_id: Client order ID (if available)
    - order_id: Exchange order ID (if available)
    - initial: Original RoutingResult snapshot (from router)
    - reconciled: OrderResult from get_order_status (if queried)
    - monitor_status: Monitor health (OK, DEGRADED, ERROR)
    - error: Error details (if UNRESOLVED/ERROR)
    - audits: List of audit records (M1, M2, M3)
    
    Audit Ordering (deterministic):
    - M1: MONITOR_INPUT (always)
    - M2: MONITOR_RECONCILE_RESULT (if reconciliation attempted)
    - M3: MONITOR_SUMMARY (always)
    """
    status: ReconciliationStatus
    ts_ms: Optional[int]
    decision_id: str
    client_order_id: Optional[str]
    order_id: Optional[str]
    initial: Dict[str, Any]
    reconciled: Optional[Dict[str, Any]]
    monitor_status: MonitorStatus
    error: Optional[Dict[str, Any]] = None
    audits: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Initialize default values."""
        if self.audits is None:
            self.audits = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "status": self.status,
            "ts_ms": self.ts_ms,
            "decision_id": self.decision_id,
            "client_order_id": self.client_order_id,
            "order_id": self.order_id,
            "initial": self.initial,
            "reconciled": self.reconciled,
            "monitor_status": self.monitor_status,
            "error": self.error,
            "audits": self.audits,
        }


# ────────────────────────────────────────────────────────────────────────────────
# HELPERS
# ────────────────────────────────────────────────────────────────────────────────

def stable_json(obj: Any) -> str:
    """
    Canonical JSON serialization (deterministic).
    
    Args:
        obj: Object to serialize
    
    Returns:
        Canonical JSON string (sorted keys, compact)
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def canonical_ts(*candidates: Optional[int]) -> Optional[int]:
    """
    Compute canonical timestamp from candidates (deterministic).
    
    Returns max of all non-None timestamps, or None if all None.
    
    Args:
        *candidates: Timestamp candidates (may be None)
    
    Returns:
        Max timestamp or None
    """
    valid = [ts for ts in candidates if ts is not None]
    return max(valid) if valid else None
