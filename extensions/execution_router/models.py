"""
PHASE 14C — EXECUTION ROUTER: Models

Deterministic routing result contracts.

CRITICAL RULES:
- Single chokepoint (gateway → router → client)
- Defense-in-depth (double kill switch)
- Audit binding (decision ↔ order)
- Fail-closed (errors never crash)
- Deterministic (stable JSON)
"""

import json
import hashlib
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, Literal, List


# ────────────────────────────────────────────────────────────────────────────────
# TYPE ALIASES
# ────────────────────────────────────────────────────────────────────────────────

RoutingStatus = Literal[
    "SUCCESS",          # Gateway ALLOWED + execution completed
    "BLOCKED",          # Gateway BLOCKED (no execution)
    "ERROR",            # Exception or failure (fail-safe)
    "PARTIAL_FAILURE",  # Execution attempted but failed
]


# ────────────────────────────────────────────────────────────────────────────────
# ROUTING ERROR
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class RoutingError:
    """
    Error details for routing failures.
    
    Fields:
    - code: Error code (deterministic string)
    - message: Human-readable message
    - details: Optional additional context
    """
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        result = {
            "code": self.code,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        return result


# ────────────────────────────────────────────────────────────────────────────────
# ROUTING RESULT
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class RoutingResult:
    """
    Result of routing execution request through gateway and client.
    
    Fields:
    - status: RoutingStatus enum
    - ts_ms: Canonical deterministic timestamp
    - decision: ExecutionDecision as dict (from gateway)
    - decision_id: Hash-based decision identifier
    - client_order_id: Deterministic client order ID
    - order_result: OrderResult as dict (if execution attempted)
    - audits: List of audit records (bounded, deterministic ordering)
    - error: RoutingError (if ERROR/PARTIAL_FAILURE)
    
    Audit Ordering (deterministic):
    - A: Gateway audit (EXECUTION_GATEWAY_EVALUATED)
    - B: Router audit (ROUTER_ROUTE_RESULT)
    - C: Execution audit (EXECUTION_RESULT) [only if execution attempted]
    """
    status: RoutingStatus
    ts_ms: Optional[int]
    decision: Dict[str, Any]
    decision_id: Optional[str]
    client_order_id: Optional[str]
    order_result: Optional[Dict[str, Any]] = None
    audits: List[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Initialize default values."""
        if self.audits is None:
            self.audits = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "status": self.status,
            "ts_ms": self.ts_ms,
            "decision": self.decision,
            "decision_id": self.decision_id,
            "client_order_id": self.client_order_id,
            "order_result": self.order_result,
            "audits": self.audits,
            "error": self.error,
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


def derive_decision_id(gateway_audit: Optional[Dict[str, Any]], decision: Dict[str, Any]) -> str:
    """
    Derive deterministic decision ID.
    
    Preference order:
    1. gateway_audit.data.context_digest (preferred)
    2. Hash of decision dict (fallback)
    
    Args:
        gateway_audit: Gateway audit payload dict (may be None)
        decision: ExecutionDecision dict
    
    Returns:
        Deterministic decision ID (16-char hex)
    """
    # Prefer context_digest from gateway audit
    if gateway_audit and isinstance(gateway_audit.get("data"), dict):
        context_digest = gateway_audit["data"].get("context_digest")
        if context_digest:
            return str(context_digest)
    
    # Fallback: hash of decision dict
    decision_json = stable_json(decision)
    return hashlib.sha256(decision_json.encode("utf-8")).hexdigest()[:16]
