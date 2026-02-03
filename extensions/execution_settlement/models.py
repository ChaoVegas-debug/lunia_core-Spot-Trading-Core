"""
PHASE 14E — EXECUTION SETTLEMENT: Models

Post-trade settlement contracts and truth extraction.

CRITICAL RULES:
- Zero double counting (idempotency)
- Truth priority (reconciliation > routing)
- Ledger-first (portfolio failure doesn't revert)
- Final-state only (FILLED/REJECTED/CANCELED)
- Deterministic (stable JSON)
- No wall-clock
"""

import json
import hashlib
from dataclasses import dataclass
from typing import Dict, Any, Optional, Literal, List, Protocol, Tuple


# ────────────────────────────────────────────────────────────────────────────────
# TYPE ALIASES
# ────────────────────────────────────────────────────────────────────────────────

SettlementStatus = Literal[
    "APPLIED",      # Successfully applied to ledger + portfolio
    "SKIPPED",      # Not applied (reason in skip_reason)
    "ERROR",        # Failed with error
]

SkipReason = Literal[
    "NOT_FINAL",         # Non-terminal status (NEW/PARTIALLY_FILLED)
    "ALREADY_APPLIED",   # Idempotency: already processed
    "MISSING_DATA",      # Missing required fields
    "BLOCKED",           # Gateway blocked (no execution)
    "NO_TRUTH",          # Cannot extract truth OrderResult
    "INVALID_SHAPE",     # Invalid structure
]


# ────────────────────────────────────────────────────────────────────────────────
# SETTLEMENT ERROR
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class SettlementError:
    """
    Error details for settlement failures.
    
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
# PORTFOLIO APPLY RESULT
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class PortfolioApplyResult:
    """
    Result of portfolio apply operation.
    
    Fields:
    - updated: Whether portfolio was updated
    - ref: Reference ID from portfolio (if applicable)
    """
    updated: bool
    ref: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "updated": self.updated,
            "ref": self.ref,
        }


# ────────────────────────────────────────────────────────────────────────────────
# PORTFOLIO SINK INTERFACE
# ────────────────────────────────────────────────────────────────────────────────

class PortfolioSink(Protocol):
    """
    Portfolio sink interface (duck-typed).
    
    Implementations must provide apply_fill method.
    """
    
    def apply_fill(self, trade: Dict[str, Any], *, idempotency_key: str) -> PortfolioApplyResult:
        """
        Apply fill to portfolio (idempotent).
        
        Args:
            trade: Trade details (symbol, side, quantity, price, fees)
            idempotency_key: Idempotency key (prevents double-apply)
        
        Returns:
            PortfolioApplyResult
        """
        ...


# ────────────────────────────────────────────────────────────────────────────────
# SETTLEMENT RESULT
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class SettlementResult:
    """
    Result of post-trade settlement.
    
    Fields:
    - status: SettlementStatus (APPLIED, SKIPPED, ERROR)
    - ts_ms: Canonical deterministic timestamp
    - decision_id: Decision ID from router
    - client_order_id: Client order ID (if available)
    - order_id: Exchange order ID (if available)
    - symbol: Trading symbol (if available)
    - truth_source: "RECONCILIATION" or "ROUTING"
    - terminal_status: FILLED/REJECTED/CANCELED or "NONE"
    - idempotency_key: Deterministic key
    - already_applied: Whether already processed
    - ledger_ref: Ledger reference (if appended)
    - portfolio_updated: Whether portfolio was updated
    - portfolio_ref: Portfolio reference (if applicable)
    - skip_reason: Reason for skip (if SKIPPED)
    - audits: List of audit records (E1, E2, E3, E4)
    - error: Error details (if ERROR)
    
    Audit Ordering (deterministic):
    - E1: SETTLEMENT_INPUT (always)
    - E2: LEDGER_APPEND (attempted or SKIPPED)
    - E3: PORTFOLIO_APPLY (attempted or SKIPPED)
    - E4: SETTLEMENT_SUMMARY (always)
    """
    status: SettlementStatus
    ts_ms: Optional[int]
    decision_id: str
    client_order_id: Optional[str]
    order_id: Optional[str]
    symbol: Optional[str]
    truth_source: str
    terminal_status: str
    idempotency_key: str
    already_applied: bool
    ledger_ref: Optional[str] = None
    portfolio_updated: bool = False
    portfolio_ref: Optional[str] = None
    skip_reason: Optional[str] = None
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
            "decision_id": self.decision_id,
            "client_order_id": self.client_order_id,
            "order_id": self.order_id,
            "symbol": self.symbol,
            "truth_source": self.truth_source,
            "terminal_status": self.terminal_status,
            "idempotency_key": self.idempotency_key,
            "already_applied": self.already_applied,
            "ledger_ref": self.ledger_ref,
            "portfolio_updated": self.portfolio_updated,
            "portfolio_ref": self.portfolio_ref,
            "skip_reason": self.skip_reason,
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


def is_terminal_status(status: Optional[str]) -> bool:
    """
    Check if status is terminal (final state).
    
    Terminal statuses (MVP): FILLED, REJECTED, CANCELED
    Non-terminal: NEW, PARTIALLY_FILLED, UNKNOWN
    
    Args:
        status: Order status string
    
    Returns:
        True if terminal, False otherwise
    """
    if not status:
        return False
    return status.upper() in ["FILLED", "REJECTED", "CANCELED"]


def derive_idempotency_key(
    decision_id: str,
    client_order_id: Optional[str],
    order_id: Optional[str],
    terminal_status: str,
    filled_qty_str: str = "0",
) -> str:
    """
    Derive deterministic idempotency key.
    
    Components (order matters):
    1. decision_id (always present)
    2. client_order_id (if present)
    3. order_id (if present)
    4. terminal_status (FILLED/REJECTED/CANCELED)
    5. filled_qty (for FILLED, to distinguish partial fills in future)
    
    Args:
        decision_id: Decision ID from router
        client_order_id: Client order ID (optional)
        order_id: Exchange order ID (optional)
        terminal_status: Terminal status
        filled_qty_str: Filled quantity as string (default "0")
    
    Returns:
        Deterministic idempotency key (16-char hex)
    """
    components = {
        "decision_id": decision_id,
        "client_order_id": client_order_id or "",
        "order_id": order_id or "",
        "terminal_status": terminal_status,
        "filled_qty": filled_qty_str if terminal_status == "FILLED" else "0",
    }
    
    key_json = stable_json(components)
    return hashlib.sha256(key_json.encode("utf-8")).hexdigest()[:16]


def extract_truth(
    routing_result: Dict[str, Any],
    reconciliation_result: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[Dict[str, Any]], str, str]:
    """
    Extract truth OrderResult from routing/reconciliation (STRICT PRIORITY).
    
    Priority rules (AXIOM A3):
    1. If reconciliation_result exists AND status == "FINAL" AND has reconciled:
       → use reconciled OrderResult (truth_source = "RECONCILIATION")
    2. Else if routing_result has order_result:
       → use routing order_result (truth_source = "ROUTING")
    3. Else:
       → NO_TRUTH (None, "NONE", "NONE")
    
    Args:
        routing_result: RoutingResult dict from Phase 14C
        reconciliation_result: ReconciliationResult dict from Phase 14D (optional)
    
    Returns:
        Tuple: (truth_order_result, truth_source, terminal_status)
               truth_order_result: OrderResult dict or None
               truth_source: "RECONCILIATION" | "ROUTING" | "NONE"
               terminal_status: Order status or "NONE"
    """
    # Priority 1: Reconciliation (if FINAL + has reconciled)
    if reconciliation_result:
        recon_status = reconciliation_result.get("status")
        reconciled = reconciliation_result.get("reconciled")
        
        if recon_status == "FINAL" and reconciled:
            terminal_status = reconciled.get("status", "NONE")
            return (reconciled, "RECONCILIATION", terminal_status)
    
    # Priority 2: Routing (if has order_result)
    order_result = routing_result.get("order_result")
    if order_result:
        terminal_status = order_result.get("status", "NONE")
        return (order_result, "ROUTING", terminal_status)
    
    # Priority 3: NO_TRUTH
    return (None, "NONE", "NONE")
