"""
Epoch C.4 — Lifecycle Recovery

Crash recovery and reconciliation for lifecycle state.
Handles orphan positions and ghost plans.
"""
from typing import List, Dict, Set
import logging

from lunia_core.app.services.state_store.models import (
    PersistedExitPlanState,
    LifecycleRegistryState,
)
from lunia_core.app.services.state_store.interfaces import StateStore
from lunia_core.app.services.lifecycle.exit_planner import ExitPlanner
from lunia_core.app.services.lifecycle.models import ExitPlan
from lunia_core.app.services.risk_governor.models import PortfolioSnapshot, Position

logger = logging.getLogger(__name__)


class LifecycleRecovery:
    """
    Recovers lifecycle state after crash/restart.
    
    Responsibilities:
    - Reconcile persisted state with live portfolio
    - Create emergency plans for orphan positions
    - Clean up ghost plans (no longer in portfolio)
    - Emit critical events for anomalies
    """
    
    def __init__(self, store: StateStore, exit_planner: ExitPlanner):
        """
        Initialize recovery manager.
        
        Args:
            store: State store for persistence
            exit_planner: Exit planner for creating emergency plans
        """
        self.store = store
        self.exit_planner = exit_planner
    
    def restore(
        self,
        snapshot: PortfolioSnapshot,
        now_ms: int,
    ) -> LifecycleRegistryState:
        """
        Restore lifecycle state from persisted data.
        
        Reconciles persisted exit plans with current portfolio snapshot.
        Handles orphans (positions without plans) and ghosts (plans without positions).
        
        Args:
            snapshot: Current portfolio snapshot
            now_ms: Current timestamp
        
        Returns:
            Reconciled lifecycle registry state
        """
        # Load persisted registry
        persisted_registry = self.store.load_registry(as_of_ms=now_ms)
        
        # Find mismatches
        orphans = self._find_orphans(persisted_registry, snapshot)
        ghosts = self._find_ghosts(persisted_registry, snapshot)
        
        # Handle orphans (CRITICAL)
        for orphan_pos in orphans:
            logger.critical(
                f"ORPHAN_POSITION_DETECTED: {orphan_pos.symbol} "
                f"(qty={orphan_pos.quantity}, entry={orphan_pos.avg_entry_price})"
            )
            emergency_plan = self._create_emergency_plan(orphan_pos, now_ms)
            self.store.upsert_exit_plan(emergency_plan)
            logger.warning(
                f"EMERGENCY_PLAN_CREATED: {orphan_pos.symbol} "
                f"SL={emergency_plan.exit_plan.stop_loss_price}"
            )
        
        # Handle ghosts (WARNING)
        for ghost_id in ghosts:
            logger.warning(f"GHOST_PLAN_DETECTED: {ghost_id} (no live position)")
            self.store.mark_closed(ghost_id, "CLOSED_EXTERNALLY", now_ms)
        
        # Reload clean registry
        clean_registry = self.store.load_registry(as_of_ms=now_ms)
        
        logger.info(
            f"RECOVERY_COMPLETE: {len(clean_registry.active_positions)} active, "
            f"{len(orphans)} orphans recovered, {len(ghosts)} ghosts cleaned"
        )
        
        return clean_registry
    
    def _find_orphans(
        self,
        registry: LifecycleRegistryState,
        snapshot: PortfolioSnapshot,
    ) -> List[Position]:
        """
        Find positions in snapshot without exit plans.
        
        These are CRITICAL: positions that exist but have no risk management.
        """
        active_symbols = set(registry.active_positions.keys())
        snapshot_symbols = {pos.symbol for pos in snapshot.positions}
        
        orphan_symbols = snapshot_symbols - active_symbols
        
        orphans = [
            pos for pos in snapshot.positions if pos.symbol in orphan_symbols
        ]
        
        return orphans
    
    def _find_ghosts(
        self,
        registry: LifecycleRegistryState,
        snapshot: PortfolioSnapshot,
    ) -> Set[str]:
        """
        Find exit plans without corresponding positions.
        
        These are WARNING-level: stale state that needs cleanup.
        """
        active_symbols = set(registry.active_positions.keys())
        snapshot_symbols = {pos.symbol for pos in snapshot.positions}
        
        ghost_symbols = active_symbols - snapshot_symbols
        
        # Return position IDs
        ghost_ids = {
            registry.active_positions[symbol].position_id
            for symbol in ghost_symbols
        }
        
        return ghost_ids
    
    def _create_emergency_plan(
        self,
        position: Position,
        now_ms: int,
    ) -> PersistedExitPlanState:
        """
        Create emergency exit plan for orphan position.
        
        Uses tight stop-loss and short time limit for maximum protection.
        
        Args:
            position: Orphaned position
            now_ms: Current timestamp
        
        Returns:
            Emergency exit plan state
        """
        # Tight SL: 0.5% from entry
        sl_pct = 0.005
        if position.side == "LONG":
            sl_price = position.avg_entry_price * (1 - sl_pct)
        else:
            sl_price = position.avg_entry_price * (1 + sl_pct)
        
        # Emergency plan: tight SL, 5-minute time limit
        emergency_exit_plan = ExitPlan(
            position_id=f"emergency_{position.symbol}_{now_ms}",
            symbol=position.symbol,
            side=position.side,
            entry_price=position.avg_entry_price,
            stop_loss_price=sl_price,
            take_profit_price=None,
            max_duration_ms=300000,  # 5 minutes
            created_at_ms=now_ms,
            last_updated_ms=now_ms,
            strategy_type="EMERGENCY_RECOVERY",
        )
        
        return PersistedExitPlanState(
            version=1,
            position_id=emergency_exit_plan.position_id,
            symbol=position.symbol,
            side=position.side,
            entry_price=position.avg_entry_price,
            quantity=position.quantity,
            exit_plan=emergency_exit_plan,
            trailing_peak_price=None,
            trailing_active=False,
            created_at_ms=now_ms,
            last_updated_ms=now_ms,
            status="RECOVERED_ORPHAN",
        )
