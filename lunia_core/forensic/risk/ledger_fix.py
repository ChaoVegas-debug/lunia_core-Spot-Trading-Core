"""Risk State Ledger (PHASE 1-4)

Passive flight recorder updated strictly AFTER Accounting.apply_fill.
Tracks HWM persistently, binds to real fills via last_trade_id.

Constitution:
- Read-only observer, never mutates Portfolio/Orders/Strategy
- Updated post-fill ONLY, never pre-trade
- All math uses Decimal
- current_equity MUST match Portfolio.equity exactly

PHASE 4 addition: Freshness metadata for API observability
"""
import json
from dataclasses import dataclass, asdict
from decimal import Decimal
from typing import Optional


@dataclass
class RiskState:
    """Risk state snapshot (read-only observation).
    
    PHASE 1 SHADOW MODE:
    - Status is observational only, never used to block
    - All financial values use Decimal
    - last_trade_id correlates with Accounting fills
    
    PHASE 4: Added freshness metadata (last_update_ts, last_decision_*)
    """
    
    run_id: str
    timestamp: float
    last_trade_id: Optional[str]
    
    # Financial state (Decimal only)
    equity_high_water_mark: Decimal  # Persistent peak within run
    current_equity: Decimal  # Read from Portfolio only
    current_drawdown_pct: Decimal  # (HWM - current) / HWM
    
    # Observational signals (never used for blocking)
    status: str  # HEALTHY | WARNING | CRITICAL | HALT_OBSERVED
    active_violation: Optional[str]  # e.g. "DRAWDOWN_25PCT"
    trades_since_peak: int
    
    # Phase 4: Freshness metadata (optional fields MUST come last for Python dataclass)
    last_update_ts: Optional[float] = None
    last_decision_id: Optional[str] = None
    last_decision_blocked: Optional[bool] = None
    last_decision_reason: Optional[str] = None
    
    def __post_init__(self):
        """Validate Decimal types."""
        if not isinstance(self.equity_high_water_mark, Decimal):
            raise TypeError(f"equity_high_water_mark must be Decimal, got {type(self.equity_high_water_mark)}")
        if not isinstance(self.current_equity, Decimal):
            raise TypeError(f"current_equity must be Decimal, got {type(self.current_equity)}")
        if not isinstance(self.current_drawdown_pct, Decimal):
            raise TypeError(f"current_drawdown_pct must be Decimal, got {type(self.current_drawdown_pct)}")
