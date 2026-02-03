"""Risk Decision Contract (PHASE 2 - Enforcement Ready)

Upgraded from Phase 1 to support actual enforcement.
Includes audit trail, override tracking, deterministic decision_id.

Constitution:
- SHADOW mode: allowed=True always, blocked=False always
- ENFORCE mode: allowed may be False when blocked
- decision_id is deterministic (no timestamps, no UUIDs)
"""
import json
import hashlib
from dataclasses import dataclass, asdict
from decimal import Decimal
from typing import Optional


@dataclass
class RiskDecision:
    """Risk assessment decision (Phase 2 - enforcement capable).
    
    PHASE 2 CHANGES:
    - Added enforcement fields (enforce_active, blocked, block_reason)
    - Added override audit trail
    - Added deterministic decision_id (SHA256)
    - Added run_id, intent_id for audit chain
    - Constitution enforced in __post_init__
    """
    
    # Audit chain
    run_id: str
    intent_id: str
    decision_id: str  # Deterministic SHA256 (no timestamps)
    
    # Mode
    mode: str  # "SHADOW" | "ENFORCE"
    enforce_active: bool
    
    # Core decision
    allowed: bool  # May be False in ENFORCE mode
    would_block: bool  # Signal from risk math
    blocked: bool  # Physical block (enforce_active AND would_block AND NOT override_valid)
    
    # Risk metrics (Decimal only - REQUIRED)
    current_dd: Decimal
    projected_dd: Decimal
    equity_hwm: Decimal
    equity_current: Decimal
    equity_projected: Decimal
    
    # Override audit (REQUIRED bools)
    override_present: bool
    override_valid: bool
    override_used: bool  # override_valid AND would_block AND enforce_active
    
    # Optional fields (must come LAST in dataclass)
    block_reason: Optional[str] = None  # CURRENT_DRAWDOWN_25PCT | PROJECTED_DRAWDOWN_25PCT | FAIL_CLOSED_ERROR | EMERGENCY_BUY_FORBIDDEN
    reason: Optional[str] = None  # Phase 1 backward compatibility (alias for block_reason)
    override_actor: Optional[str] = None
    override_reason: Optional[str] = None
    
    # Phase 3: Emergency bypass audit
    is_emergency_bypass: bool = False
    emergency_reason: Optional[str] = None  # e.g. "PANIC_BUTTON_LIQUIDATION"
    
    def __post_init__(self):
        """Enforce PHASE 2 constitution."""
        # Phase 1 backward compatibility: sync reason with block_reason
        if self.reason is None and self.block_reason is not None:
            # Use block_reason as reason for Phase 1 tests
            object.__setattr__(self, 'reason', self.block_reason)
        elif self.reason is not None and self.block_reason is None:
            # Allow Phase 1 tests to use reason= kwarg
            object.__setattr__(self, 'block_reason', self.reason)
        
        # SHADOW mode invariants
        if self.mode == "SHADOW":
            if not self.allowed:
                raise RuntimeError(
                    "[PHASE2_FAIL] SHADOW mode MUST have allowed=True. "
                    f"Got allowed={self.allowed}. "
                    "This is a constitution violation."
                )
            if self.blocked:
                raise RuntimeError(
                    "[PHASE2_FAIL] SHADOW mode MUST have blocked=False. "
                    f"Got blocked={self.blocked}. "
                    "This is a constitution violation."
                )
        
        # decision_id must be non-empty
        if not self.decision_id or self.decision_id == "pending":
            raise RuntimeError(
                "[PHASE2_FAIL] decision_id must be deterministic and non-empty. "
                f"Got: '{self.decision_id}'"
            )
        
        # Type validation (Decimal only)
        if not isinstance(self.current_dd, Decimal):
            raise TypeError(f"current_dd must be Decimal, got {type(self.current_dd)}")
        if not isinstance(self.projected_dd, Decimal):
            raise TypeError(f"projected_dd must be Decimal, got {type(self.projected_dd)}")
        if not isinstance(self.equity_hwm, Decimal):
            raise TypeError(f"equity_hwm must be Decimal, got {type(self.equity_hwm)}")
        if not isinstance(self.equity_current, Decimal):
            raise TypeError(f"equity_current must be Decimal, got {type(self.equity_current)}")
        if not isinstance(self.equity_projected, Decimal):
            raise TypeError(f"equity_projected must be Decimal, got {type(self.equity_projected)}")


def compute_decision_id(
    run_id: str,
    intent_id: str,
    mode: str,
    max_drawdown: Decimal,
    equity_hwm: Decimal,
    equity_current: Decimal,
    equity_projected: Decimal,
    current_dd: Decimal,
    projected_dd: Decimal,
    would_block: bool,
    block_reason: Optional[str],
    override_present: bool,
    override_valid: bool,
    salt: str = "PHASE2_AUDIT"
) -> str:
    """Compute deterministic decision_id (SHA256, truncated).
    
    NO timestamps, NO UUIDs, NO random values.
    Canonical snapshot with sorted keys.
    
    Args:
        All decision inputs (Decimal values)
        
    Returns:
        16-char hex SHA256 (deterministic)
    """
    # Canonical snapshot (Decimal -> str, sorted keys)
    snapshot = {
        "run_id": run_id,
        "intent_id": intent_id,
        "mode": mode,
        "max_drawdown": str(max_drawdown),
        "equity_hwm": str(equity_hwm),
        "equity_current": str(equity_current),
        "equity_projected": str(equity_projected),
        "current_dd": str(current_dd),
        "projected_dd": str(projected_dd),
        "would_block": would_block,
        "block_reason": block_reason,
        "override_present": override_present,
        "override_valid": override_valid,
        "salt": salt,
    }
    
    # Canonical JSON (sorted keys, no whitespace, str conversion)
    canonical_json = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    
    # SHA256 hash (truncated to 16 chars)
    hash_bytes = hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()
    
    return hash_bytes[:16]
