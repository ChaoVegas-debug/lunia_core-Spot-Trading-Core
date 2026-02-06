"""
Lifecycle Manager — Autonomous Position Lifecycle Orchestration

Coordinates:
- Position sizing (AllocationEngine)
- Exit plan creation (ExitPlanner)
- Exit monitoring (ExitMonitor)
- Order intent generation

CRITICAL: All generated intents MUST flow through Council → Risk Governor
(no direct execution bypass)
"""
import logging
from typing import Dict, List, Optional

from lunia_core.app.services.lifecycle.allocation import AllocationEngine
from lunia_core.app.services.lifecycle.exit_monitor import ExitIntent, ExitMonitor
from lunia_core.app.services.lifecycle.exit_planner import ExitPlanner
from lunia_core.app.services.lifecycle.models import (
    AllocationPolicy,
    ExitPlan,
    VolatilityRegime,
)
from lunia_core.app.services.risk_governor.models import PortfolioSnapshot

logger = logging.getLogger(__name__)


class LifecycleManager:
    """
    Autonomous position lifecycle manager.
    
    Responsibilities:
    1. Calculate entry sizes (deterministic)
    2. Create mandatory exit plans at entry
    3. Monitor active positions
    4. Generate exit intents when triggers hit
    
    State:
    - active_plans: In-memory exit plan registry (v1)
    
    Future (Epoch C.4+):
    - Persistent storage
    - Multi-leg exits
    - Regime-based invalidation
    """
    
    def __init__(
        self,
        policy: Optional[AllocationPolicy] = None,
    ):
        """
        Initialize lifecycle manager.
        
        Args:
            policy: Allocation policy (defaults to conservative)
        """
        self.policy = policy or AllocationPolicy()
        self.allocation_engine = AllocationEngine(self.policy)
        self.exit_planner = ExitPlanner()
        self.exit_monitor = ExitMonitor()
        
        # In-memory state (v1)
        self.active_plans: Dict[str, ExitPlan] = {}
        
        logger.info(
            f"📊 LifecycleManager initialized "
            f"(base_unit={self.policy.base_unit_pct*100:.1f}%)"
        )
    
    def calculate_entry_size(
        self,
        total_equity: float,
        strategy_confidence: float,
        volatility_regime: VolatilityRegime,
        reference_price: float,
    ) -> Optional[float]:
        """
        Calculate position size.
        
        Returns quantity in base currency, or None if below minimum.
        
        This is a passthrough to AllocationEngine for convenience.
        """
        return self.allocation_engine.calculate_entry_size(
            total_equity=total_equity,
            strategy_confidence=strategy_confidence,
            volatility_regime=volatility_regime,
            reference_price=reference_price,
        )
    
    def on_fill(
        self,
        position_id: str,
        symbol: str,
        side: str,
        entry_price: float,
        quantity: float,
        strategy_type: str,
        atr: Optional[float],
        now_ms: int,
    ) -> ExitPlan:
        """
        Create exit plan immediately after position fill.
        
        MANDATORY: Position without ExitPlan is INVALID.
        
        Args:
            position_id: Unique position identifier
            symbol: Trading symbol
            side: LONG or SHORT
            entry_price: Fill price
            quantity: Position size
            strategy_type: TREND, MEAN_REVERSION, or BREAKOUT
            atr: Average True Range
            now_ms: Fill timestamp
        
        Returns:
            Immutable ExitPlan
        
        Raises:
            ValueError: If exit plan cannot be created
        """
        logger.info(
            f"📝 Creating exit plan: {symbol} {side} {quantity} @ {entry_price} "
            f"[{strategy_type}]"
        )
        
        plan = self.exit_planner.create_exit_plan(
            position_id=position_id,
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            strategy_type=strategy_type,
            atr=atr,
            now_ms=now_ms,
        )
        
        # Register active plan
        self.active_plans[symbol] = plan
        
        logger.info(
            f"✅ Exit plan registered: {symbol} "
            f"(SL={plan.stop_loss_price}, TP={plan.take_profit_price})"
        )
        
        return plan
    
    def on_tick(
        self,
        snapshot: PortfolioSnapshot,
        now_ms: int,
    ) -> List[ExitIntent]:
        """
        Evaluate all exit plans and generate exit orders.
        
        Called on every market data tick.
        
        Args:
            snapshot: Current portfolio state
            now_ms: Current timestamp
        
        Returns:
            List of exit intents to send to Council
        """
        if not self.active_plans:
            return []
        
        exit_intents, updated_plans = self.exit_monitor.evaluate_exits(
            exit_plans=self.active_plans,
            snapshot=snapshot,
            now_ms=now_ms,
        )
        
        # Update trailing stops
        if updated_plans:
            self.active_plans.update(updated_plans)
            logger.debug(
                f"📈 Updated {len(updated_plans)} trailing stop(s)"
            )
        
        if exit_intents:
            logger.info(
                f"🚪 Generated {len(exit_intents)} exit intent(s)"
            )
        
        return exit_intents
    
    def get_active_plan(self, symbol: str) -> Optional[ExitPlan]:
        """Get active exit plan for symbol"""
        return self.active_plans.get(symbol)
    
    def remove_plan(self, symbol: str) -> None:
        """Remove exit plan (after position closed)"""
        if symbol in self.active_plans:
            del self.active_plans[symbol]
            logger.info(f"🗑️ Exit plan removed: {symbol}")
    
    def get_all_plans(self) -> Dict[str, ExitPlan]:
        """Get all active exit plans"""
        return self.active_plans.copy()
