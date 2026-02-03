"""
PHASE 13A — SHADOW RUNNER: Models

Deterministic data contracts for shadow execution.
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, Literal


# ────────────────────────────────────────────────────────────────────────────────
# TYPE ALIASES
# ────────────────────────────────────────────────────────────────────────────────

SignalType = Literal["NOOP", "ENTRY_BUY", "ENTRY_SELL", "EXIT"]
ShadowStatus = Literal["EXECUTED", "SKIPPED_STALE", "SKIPPED_NOOP", "ERROR"]
SideType = Literal["BUY", "SELL"]
ActionType = Literal["ENTRY", "EXIT"]

# ────────────────────────────────────────────────────────────────────────────────
# STRATEGY INTENT (Normalized)
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class StrategyIntent:
    """Normalized strategy intent from execute_genome."""
    signal: SignalType
    confidence: float
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return asdict(self)


# ────────────────────────────────────────────────────────────────────────────────
# VIRTUAL ORDER SPEC (Immediate Fill)
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class VirtualOrderSpec:
    """Virtual order specification (immediate fill model)."""
    symbol: str
    side: SideType
    action: ActionType
    fill_price: str
    price_type: Literal["IMMEDIATE_FILL"]
    reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return asdict(self)


# ────────────────────────────────────────────────────────────────────────────────
# SHADOW STEP RESULT
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class ShadowStepResult:
    """Result of one shadow loop tick."""
    timestamp_ms: Optional[int]
    symbol: str
    status: ShadowStatus
    snapshot_health: Dict[str, Any]
    decision_id: Optional[str] = None
    intent: Optional[StrategyIntent] = None
    virtual_order: Optional[VirtualOrderSpec] = None
    audit_ref: str = ""
    error: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        result = asdict(self)
        # Convert nested dataclasses
        if self.intent:
            result["intent"] = self.intent.to_dict()
        if self.virtual_order:
            result["virtual_order"] = self.virtual_order.to_dict()
        return result


# ────────────────────────────────────────────────────────────────────────────────
# ERROR CODES
# ────────────────────────────────────────────────────────────────────────────────

class ShadowErrorCode:
    """Error code constants."""
    SNAPSHOT_STALE = "SNAPSHOT_STALE"
    SNAPSHOT_MISSING = "SNAPSHOT_MISSING"
    PRICE_MISSING = "PRICE_MISSING"
    PRICE_INVALID = "PRICE_INVALID"
    INTENT_INVALID = "INTENT_INVALID"
    EXECUTION_ERROR = "EXECUTION_ERROR"
    AUDIT_WRITE_FAILED = "AUDIT_WRITE_FAILED"
