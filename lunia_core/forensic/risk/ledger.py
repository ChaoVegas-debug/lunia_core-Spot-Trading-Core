"""Risk State Ledger (PHASE 1 - Shadow Mode)

Passive flight recorder updated strictly AFTER Accounting.apply_fill.
Tracks HWM persistently, binds to real fills via last_trade_id.

Constitution:
- Read-only observer, never mutates Portfolio/Orders/Strategy
- Updated post-fill ONLY, never pre-trade
- All math uses Decimal
- current_equity MUST match Portfolio.equity exactly
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
    
    # Phase 4: Freshness metadata (optional fields must come last)
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


class RiskLedger:
    """Passive risk state ledger (post-fill observer only).
    
    PHASE 1 SHADOW MODE:
    - Initialized once per run
    - Updated post-fill ONLY
    - Never mutates Portfolio
    - Never blocks execution
    - Emits structured logs for every update
    """
    
    def __init__(self):
        self._initialized = False
        self._state: Optional[RiskState] = None
    
    def initialize(self, run_id: str, initial_equity: Decimal):
        """Initialize ledger for a new run.
        
        Args:
            run_id: Unique run identifier
            initial_equity: Starting equity from Portfolio
            
        Raises:
            RuntimeError: If already initialized
            TypeError: If initial_equity is not Decimal
        """
        if self._initialized:
            raise RuntimeError(
                "[PHASE1_FAIL] RiskLedger.initialize called twice. "
                "Ledger must be initialized once per run only."
            )
        
        if not isinstance(initial_equity, Decimal):
            raise TypeError(f"initial_equity must be Decimal, got {type(initial_equity)}")
        
        self._state = RiskState(
            run_id=run_id,
            timestamp=0.0,
            last_trade_id=None,
            equity_high_water_mark=initial_equity,
            current_equity=initial_equity,
            current_drawdown_pct=Decimal("0"),
            status="HEALTHY",
            active_violation=None,
            trades_since_peak=0,
            last_update_ts=None,  # Phase 4
            last_decision_id=None,
            last_decision_blocked=None,
            last_decision_reason=None
        )
        
        self._initialized = True
        self._log_state_update()
    
    def get_state(self) -> RiskState:
        """Get current risk state (read-only).
        
        Returns:
            RiskState snapshot
            
        Raises:
            RuntimeError: If not initialized
        """
        if not self._initialized or self._state is None:
            raise RuntimeError(
                "[PHASE1_FAIL] RiskLedger.get_state called before initialize. "
                "Ledger must be initialized first."
            )
        
        return self._state
    
    def update_post_fill(self, trade_id: str, portfolio_equity: Decimal):
        """Update ledger AFTER Accounting.apply_fill.
        
        Args:
            trade_id: Fill ID from Accounting
            portfolio_equity: Equity from Portfolio.calculate_equity()
            
        Raises:
            RuntimeError: If not initialized
            TypeError: If portfolio_equity is not Decimal
        """
        if not self._initialized or self._state is None:
            raise RuntimeError(
                "[PHASE1_FAIL] RiskLedger.update_post_fill called before initialize."
            )
        
        if not isinstance(portfolio_equity, Decimal):
            raise TypeError(f"portfolio_equity must be Decimal, got {type(portfolio_equity)}")
        
        # Update state
        old_hwm = self._state.equity_high_water_mark
        
        # HWM is monotonic (never decreases)
        new_hwm = max(old_hwm, portfolio_equity)
        
        # Compute drawdown
        if new_hwm > Decimal("0"):
            drawdown_pct = (new_hwm - portfolio_equity) / new_hwm
        else:
            drawdown_pct = Decimal("0")
        
        # Status mapping
        status, violation = self._compute_status(drawdown_pct)
        
        # Trades since peak
        if portfolio_equity >= new_hwm:
            trades_since_peak = 0
        else:
            trades_since_peak = self._state.trades_since_peak + 1
        
        # Create new state
        self._state = RiskState(
            run_id=self._state.run_id,
            timestamp=self._state.timestamp + 1,  # Increment per update
            last_trade_id=trade_id,
            equity_high_water_mark=new_hwm,
            current_equity=portfolio_equity,
            current_drawdown_pct=drawdown_pct,
            status=status,
            active_violation=violation,
            trades_since_peak=trades_since_peak,
            last_update_ts=self._state.last_update_ts,  # Preserve Phase 4 metadata
            last_decision_id=self._state.last_decision_id,
            last_decision_blocked=self._state.last_decision_blocked,
            last_decision_reason=self._state.last_decision_reason
        )
        
        self._log_state_update()
    
    def _compute_status(self, drawdown_pct: Decimal) -> tuple[str, Optional[str]]:
        """Compute observational status from drawdown.
        
        Args:
            drawdown_pct: Current drawdown as Decimal
            
        Returns:
            (status, active_violation) tuple
        """
        if drawdown_pct < Decimal("0.10"):
            return ("HEALTHY", None)
        elif drawdown_pct < Decimal("0.20"):
            return ("WARNING", None)
        elif drawdown_pct < Decimal("0.25"):
            return ("CRITICAL", None)
        else:
            return ("HALT_OBSERVED", "DRAWDOWN_25PCT")
    
    def _log_state_update(self):
        """Emit structured log: [RISK_STATE_UPDATE]"""
        if self._state is None:
            return
        
        # Convert Decimal to string for JSON serialization
        state_dict = asdict(self._state)
        state_dict['equity_high_water_mark'] = str(state_dict['equity_high_water_mark'])
        state_dict['current_equity'] = str(state_dict['current_equity'])
        state_dict['current_drawdown_pct'] = str(state_dict['current_drawdown_pct'])
        
        print(f"[RISK_STATE_UPDATE] {json.dumps(state_dict)}")
    
    def record_decision(self, decision: 'RiskDecision'):
        """Record last decision for freshness tracking (Phase 4).
        
        Args:
            decision: RiskDecision from gate.assess
        """
        import time
        
        if self._state is None:
            return
        
        # Update freshness metadata
        self._state = RiskState(
            run_id=self._state.run_id,
            timestamp=self._state.timestamp,
            last_trade_id=self._state.last_trade_id,
            equity_high_water_mark=self._state.equity_high_water_mark,
            current_equity=self._state.current_equity,
            current_drawdown_pct=self._state.current_drawdown_pct,
            status=self._state.status,
            active_violation=self._state.active_violation,
            trades_since_peak=self._state.trades_since_peak,
            last_update_ts=time.time(),  # Phase 4: freshness timestamp
            last_decision_id=decision.decision_id,
            last_decision_blocked=decision.blocked,
            last_decision_reason=decision.block_reason
        )
