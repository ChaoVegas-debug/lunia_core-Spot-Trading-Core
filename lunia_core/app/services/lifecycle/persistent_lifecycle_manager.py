"""
Epoch C.4 — Persistent Lifecycle Manager

Wrapper around LifecycleManager with persistent state storage and idempotency.
"""
import hashlib
import logging
from typing import Optional, List

from lunia_core.app.services.state_store.models import PersistedExitPlanState
from lunia_core.app.services.state_store.interfaces import StateStore
from lunia_core.app.services.lifecycle.lifecycle_manager import LifecycleManager
from lunia_core.app.services.lifecycle.lifecycle_recovery import LifecycleRecovery
from lunia_core.app.services.lifecycle.models import AllocationPolicy, ExitPlan
from lunia_core.app.services.lifecycle.exit_monitor import ExitIntent
from lunia_core.app.services.risk_governor.models import PortfolioSnapshot

logger = logging.getLogger(__name__)


class PersistentLifecycleManager:
    """
    Persistent wrapper around LifecycleManager.
    
    Adds:
    - State persistence to SQLite
    - Crash recovery with orphan handling
    - Idempotency for exit intents
    - Fail-closed behavior on store failure
    """
    
    DEFAULT_IDEMPOTENCY_TTL_MS = 86400000  # 24 hours
    
    def __init__(
        self,
        store: StateStore,
        policy: Optional[AllocationPolicy] = None,
        idempotency_ttl_ms: int = DEFAULT_IDEMPOTENCY_TTL_MS,
    ):
        """
        Initialize persistent lifecycle manager.
        
        Args:
            store: State store for persistence
            policy: Allocation policy (optional)
            idempotency_ttl_ms: TTL for idempotency keys (default 24h)
        """
        self.store = store
        self.inner = LifecycleManager(policy=policy)
        self.idempotency_ttl_ms = idempotency_ttl_ms
        self.recovery = LifecycleRecovery(store, self.inner.exit_planner)
        self.store_available = True
    
    def restore_from_crash(self, snapshot: PortfolioSnapshot, now_ms: int) -> None:
        """
        Restore state after crash/restart.
        
        Reconciles persisted state with live portfolio.
        Creates emergency plans for orphan positions.
        
        Args:
            snapshot: Current portfolio snapshot
            now_ms: Current timestamp
        """
        try:
            registry = self.recovery.restore(snapshot, now_ms)
            
            # Rebuild inner manager's active plans
            for symbol, persisted in registry.active_positions.items():
                self.inner.active_plans[symbol] = persisted.exit_plan
            
            logger.info(
                f"LIFECYCLE_RESTORED: {len(registry.active_positions)} active plans"
            )
        except Exception as e:
            logger.critical(f"RECOVERY_FAILED: {e}")
            self.store_available = False
            raise
    
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
        Create exit plan on position fill.
        
        Delegates to inner manager then persists state.
        
        Args:
            position_id: Unique position ID
            symbol: Trading symbol
            side: Position side (LONG/SHORT)
            entry_price: Entry price
            quantity: Position quantity
            strategy_type: Strategy type
            atr: Average True Range
            now_ms: Current timestamp
        
        Returns:
            Created exit plan
        """
        # Delegate to inner
        plan = self.inner.on_fill(
            position_id=position_id,
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            quantity=quantity,
            strategy_type=strategy_type,
            atr=atr,
            now_ms=now_ms,
        )
        
        # Persist
        if self.store_available:
            try:
                state = PersistedExitPlanState(
                    version=1,
                    position_id=position_id,
                    symbol=symbol,
                    side=side,
                    entry_price=entry_price,
                    quantity=quantity,
                    exit_plan=plan,
                    trailing_peak_price=None,
                    trailing_active=False,
                    created_at_ms=now_ms,
                    last_updated_ms=now_ms,
                    status="ACTIVE",
                )
                self.store.upsert_exit_plan(state)
                logger.info(f"EXIT_PLAN_PERSISTED: {symbol}")
            except Exception as e:
                logger.error(f"PERSIST_FAILED: {e}")
                self.store_available = False
                # Continue - plan is in memory
        
        return plan
    
    def on_tick(
        self,
        snapshot: PortfolioSnapshot,
        now_ms: int,
    ) -> List[ExitIntent]:
        """
        Evaluate exits on market tick.
        
        Deduplicates exit intents via idempotency keys.
        Persists trailing stop updates.
        
        Args:
            snapshot: Current portfolio snapshot
            now_ms: Current timestamp
        
        Returns:
            List of deduplicated exit intents
        """
        # Evaluate exits via inner manager
        raw_intents = self.inner.on_tick(snapshot, now_ms)
        
        # Deduplicate via idempotency
        deduplicated = []
        for intent in raw_intents:
            if self._should_allow_intent(intent, now_ms):
                deduplicated.append(intent)
            else:
                logger.warning(
                    f"EXIT_INTENT_DUPLICATE: {intent.symbol} {intent.reason} (dropped)"
                )
        
        # Persist trailing stop updates
        if self.store_available:
            try:
                self._persist_trailing_updates(now_ms)
            except Exception as e:
                logger.error(f"TRAILING_PERSIST_FAILED: {e}")
                # Continue - state is in memory
        
        return deduplicated
    
    def on_exit_executed(
        self,
        position_id: str,
        intent_key: str,
        now_ms: int,
    ) -> None:
        """
        Mark exit as executed.
        
        Commits idempotency key and marks plan closed.
        
        Args:
            position_id: Position ID
            intent_key: Idempotency key
            now_ms: Execution timestamp
        """
        if not self.store_available:
            logger.warning("STORE_UNAVAILABLE: Cannot commit exit")
            return
        
        try:
            self.store.commit_idempotency(intent_key, now_ms)
            self.store.mark_closed(position_id, "EXIT_EXECUTED", now_ms)
            logger.info(f"EXIT_COMMITTED: {position_id}")
        except Exception as e:
            logger.error(f"COMMIT_FAILED: {e}")
    
    def purge_expired_keys(self, now_ms: int) -> int:
        """
        Purge expired idempotency keys.
        
        Args:
            now_ms: Current timestamp
        
        Returns:
            Number of keys purged
        """
        if not self.store_available:
            return 0
        
        try:
            purged = self.store.purge_idempotency(now_ms)
            if purged > 0:
                logger.info(f"IDEMPOTENCY_PURGED: {purged} keys")
            return purged
        except Exception as e:
            logger.error(f"PURGE_FAILED: {e}")
            return 0
    
    def calculate_entry_size(self, *args, **kwargs):
        """Delegate to inner manager."""
        return self.inner.calculate_entry_size(*args, **kwargs)
    
    def get_active_plan(self, symbol: str) -> Optional[ExitPlan]:
        """Delegate to inner manager."""
        return self.inner.get_active_plan(symbol)
    
    def get_all_plans(self) -> dict:
        """Delegate to inner manager."""
        return self.inner.get_all_plans()
    
    def remove_plan(self, symbol: str) -> None:
        """Delegate to inner manager."""
        return self.inner.remove_plan(symbol)
    
    def _should_allow_intent(self, intent: ExitIntent, now_ms: int) -> bool:
        """
        Check if exit intent should be allowed (idempotency check).
        
        Returns True if this is a new intent, False if duplicate.
        """
        if not self.store_available:
            # Fail-open for exits if store unavailable
            logger.warning("STORE_UNAVAILABLE: Allowing exit (no deduplication)")
            return True
        
        try:
            key = self._make_idempotency_key(intent, now_ms)
            payload_hash = self._hash_intent(intent)
            
            reserved = self.store.reserve_idempotency(
                key, payload_hash, now_ms, self.idempotency_ttl_ms
            )
            
            if reserved:
                logger.debug(f"EXIT_INTENT_RESERVED: {key}")
                return True
            else:
                return False
        except Exception as e:
            logger.error(f"IDEMPOTENCY_CHECK_FAILED: {e}")
            # Fail-open for exits
            return True
    
    def _make_idempotency_key(self, intent: ExitIntent, now_ms: int) -> str:
        """
        Create idempotency key from exit intent.
        
        Format: EXIT:{symbol}:{reason}:{time_bucket}
        
        Note: ExitIntent has no price or position_id,
        so we use symbol + reason + time bucket only.
        """
        time_bucket = now_ms // 1000  # 1-second buckets
        
        return f"EXIT:{intent.symbol}:{intent.reason}:{time_bucket}"
    
    def _hash_intent(self, intent: ExitIntent) -> str:
        """Create SHA256 hash of intent payload."""
        data = f"{intent.symbol}:{intent.side}:{intent.quantity}:{intent.reason}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    def _persist_trailing_updates(self, now_ms: int) -> None:
        """Persist trailing stop state updates."""
        if not self.store_available:
            return
        
        # Check each active plan for trailing updates
        active_plans = self.store.list_active(as_of_ms=now_ms)
        
        for persisted in active_plans:
            # Check if inner manager has updated trailing state
            inner_plan = self.inner.active_plans.get(persisted.symbol)
            if inner_plan is None:
                continue
            
            # Compare trailing state
            needs_update = False
            new_peak = persisted.trailing_peak_price
            
            if inner_plan.trailing_stop_peak_price != persisted.trailing_peak_price:
                needs_update = True
                new_peak = inner_plan.trailing_stop_peak_price
            
            if needs_update:
                updated_state = PersistedExitPlanState(
                    version=persisted.version,
                    position_id=persisted.position_id,
                    symbol=persisted.symbol,
                    side=persisted.side,
                    entry_price=persisted.entry_price,
                    quantity=persisted.quantity,
                    exit_plan=inner_plan,  # Updated plan
                    trailing_peak_price=new_peak,
                    trailing_active=persisted.trailing_active,
                    created_at_ms=persisted.created_at_ms,
                    last_updated_ms=now_ms,
                    status=persisted.status,
                )
                self.store.upsert_exit_plan(updated_state)
                logger.debug(f"TRAILING_UPDATED: {persisted.symbol}")
