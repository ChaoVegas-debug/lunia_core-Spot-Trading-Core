"""
EPOCH E Phase E1: Strategy Engine
Sandboxed, version-driven strategy orchestrator with zero execution authority
"""
from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional, Tuple

from ..market_data.realtime.synchronous import ThreadSafeSnapshotCache
from ..market_data.realtime.models import SnapshotState

from .interfaces import IStrategy
from .models import StrategyContext, IntentProposal
from .registry import StrategyRegistry


logger = logging.getLogger(__name__)


class StrategyEngine:
    """
    Strategy Engine orchestrator
    
    Responsibilities:
    - Consume ThreadSafeSnapshotCache (read-only)
    - Track last_processed_version per (strategy_id, symbol)
    - Build StrategyContext
    - Enforce snapshot.state == VALID
    - Sandbox strategy execution (try/except)
    - Collect IntentProposals
    - Expose results upstream (NO execution)
    
    LOCKED INVARIANTS:
    - ZERO EXECUTION AUTHORITY (no adapter, no worker, no queue access)
    - READ-ONLY DATA (market data via immutable StrategyContext)
    - STRATEGY SANDBOXING (exceptions isolated, disable only broken strategy)
    - VERSION-BASED TRIGGERING (evaluate only on new snapshot versions)
    - FAIL-SILENT (skip evaluation on STALE/INVALID snapshots)
    - GOVERNANCE PRIMACY (outputs are passive IntentProposals)
    
    Architecture:
        ThreadSafeSnapshotCache (read-only)
              ↓
        StrategyEngine (orchestrator)
              ↓
        IStrategy.on_tick(context)
              ↓
        IntentProposal (passive output)
              ↓
        (Governance decides whether to act)
    """
    
    def __init__(
        self,
        snapshot_cache: ThreadSafeSnapshotCache,
        registry: StrategyRegistry,
        persistence_hook=None  # Phase 8.2A: Optional IntentPersistenceHook
    ):
        """
        Initialize strategy engine
        
        Args:
            snapshot_cache: Thread-safe snapshot cache (read-only)
            registry: Strategy registry
            persistence_hook: Optional IntentPersistenceHook for Phase 8.2A wiring
        """
        self.snapshot_cache = snapshot_cache
        self.registry = registry
        self._persistence_hook = persistence_hook  # Phase 8.2A
        
        # Version tracking: (strategy_id, symbol) -> last_processed_version
        self._last_processed_version: Dict[Tuple[str, str], int] = {}
        
        # Disabled strategies (auto-disabled on exception)
        self._auto_disabled: set[str] = set()
        
        # Lifecycle
        self._running = False
        
        logger.info("StrategyEngine initialized")
    
    def evaluate_all(self, symbols: Optional[List[str]] = None) -> List[IntentProposal]:
        """
        Evaluate all enabled strategies on all/specified symbols
        
        Args:
            symbols: Symbols to evaluate (None = all symbols in cache)
        
        Returns:
            List of IntentProposals (passive outputs)
        """
        if symbols is None:
            symbols = self.snapshot_cache.get_all_symbols()
        
        proposals = []
        
        for symbol in symbols:
            # Get snapshot (O(1), non-blocking)
            snapshot = self.snapshot_cache.get(symbol)
            
            # Fail-silent: skip if snapshot missing or invalid
            if snapshot is None:
                logger.debug(f"Skipping {symbol}: snapshot missing")
                continue
            
            if snapshot.snapshot_state != SnapshotState.VALID:
                logger.debug(f"Skipping {symbol}: snapshot state={snapshot.snapshot_state.value}")
                continue
            
            # Evaluate all enabled strategies
            for strategy in self.registry.get_enabled_strategies():
                # Skip auto-disabled strategies
                if strategy.strategy_id in self._auto_disabled:
                    continue
                
                # Version-based triggering (CPU safety)
                last_version = self._last_processed_version.get((strategy.strategy_id, symbol), -1)
                
                if snapshot.version <= last_version:
                    # Skip: snapshot version unchanged
                    continue
                
                # Build strategy context (immutable input)
                context = StrategyContext(
                    symbol=symbol,
                    snapshot=snapshot,  # Deep copy from cache
                    snapshot_version=snapshot.version,
                    received_at_ms=int(time.time() * 1000)
                )
                
                # Sandboxed evaluation (exception isolation)
                try:
                    proposal = strategy.on_tick(context)
                    
                    if proposal is not None:
                        proposals.append(proposal)
                        
                        # Phase 8.2A: Persist intent to ExecutionJournal (fail-safe)
                        if hasattr(self, '_persistence_hook') and self._persistence_hook is not None:
                            try:
                                self._persistence_hook.persist_intent(
                                    intent=proposal,
                                    snapshot=snapshot,
                                    rationale=f"Strategy {strategy.strategy_id} on_tick evaluation"
                                )
                            except Exception as persist_err:
                                # FAIL-SAFE: persistence errors NEVER crash strategy engine
                                logger.error(
                                    f"Intent persistence failed (non-fatal): {strategy.strategy_id}:{symbol}: {persist_err}"
                                )
                        
                        logger.info(
                            f"Intent generated: {strategy.strategy_id} {symbol} "
                            f"{proposal.side} strength={proposal.signal_strength}"
                        )
                    
                    # Update version tracking (successful evaluation)
                    self._last_processed_version[(strategy.strategy_id, symbol)] = snapshot.version
                
                except Exception as e:
                    # SANDBOXING: isolate exception, disable ONLY this strategy
                    logger.error(
                        f"Strategy exception: {strategy.strategy_id} on {symbol}: {e}",
                        exc_info=True
                    )
                    
                    # Auto-disable broken strategy
                    self._auto_disabled.add(strategy.strategy_id)
                    self.registry.disable(strategy.strategy_id)
                    
                    logger.warning(f"Strategy auto-disabled due to exception: {strategy.strategy_id}")
                    
                    # Engine continues running (isolation verified)
        
        return proposals
    
    def initialize_strategies(self, symbols: List[str]):
        """
        Initialize all enabled strategies with current snapshots
        
        Args:
            symbols: Symbols to initialize
        """
        logger.info(f"Initializing strategies for {len(symbols)} symbols...")
        
        for symbol in symbols:
            snapshot = self.snapshot_cache.get(symbol)
            
            if snapshot is None or snapshot.snapshot_state != SnapshotState.VALID:
                logger.warning(f"Skipping initialization for {symbol}: invalid snapshot")
                continue
            
            context = StrategyContext(
                symbol=symbol,
                snapshot=snapshot,
                snapshot_version=snapshot.version,
                received_at_ms=int(time.time() * 1000)
            )
            
            for strategy in self.registry.get_enabled_strategies():
                try:
                    strategy.on_init(context)
                    logger.info(f"Strategy initialized: {strategy.strategy_id} on {symbol}")
                except Exception as e:
                    logger.error(
                        f"Initialization error: {strategy.strategy_id} on {symbol}: {e}",
                        exc_info=True
                    )
                    self._auto_disabled.add(strategy.strategy_id)
                    self.registry.disable(strategy.strategy_id)
        
        logger.info("Strategy initialization complete")
    
    def reset_version_tracking(self, strategy_id: Optional[str] = None):
        """
        Reset version tracking (force re-evaluation)
        
        Args:
            strategy_id: Strategy ID (None = reset all)
        """
        if strategy_id is None:
            self._last_processed_version.clear()
            logger.info("Version tracking reset (all strategies)")
        else:
            self._last_processed_version = {
                k: v
                for k, v in self._last_processed_version.items()
                if k[0] != strategy_id
            }
            logger.info(f"Version tracking reset: {strategy_id}")
    
    def get_auto_disabled(self) -> set[str]:
        """
        Get set of auto-disabled strategies
        
        Returns:
            Set of strategy IDs
        """
        return self._auto_disabled.copy()
    
    def re_enable(self, strategy_id: str):
        """
        Re-enable an auto-disabled strategy (clears exception state)
        
        Args:
            strategy_id: Strategy ID
        """
        if strategy_id in self._auto_disabled:
            self._auto_disabled.remove(strategy_id)
            self.registry.enable(strategy_id)
            self.reset_version_tracking(strategy_id)
            logger.info(f"Strategy re-enabled: {strategy_id}")
        else:
            logger.warning(f"Strategy not auto-disabled: {strategy_id}")
