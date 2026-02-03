"""
EPOCH E Phase E1: Strategy Engine Core Tests
"""
import pytest
import time

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.strategy.interfaces import IStrategy
from app.services.strategy.models import StrategyContext, IntentProposal, SignalSide
from app.services.strategy.registry import StrategyRegistry
from app.services.strategy.engine import StrategyEngine

from app.services.market_data.realtime.synchronous import ThreadSafeSnapshotCache
from app.services.market_data.realtime.models import MarketSnapshot, SnapshotState


# Mock strategy implementation for testing
class MockStrategy(IStrategy):
    def __init__(self, strategy_id: str, version: str = "1.0.0"):
        self._strategy_id = strategy_id
        self._version = version
        self._init_called = False
        self._tick_called_count = 0
        self._stop_called = False
    
    @property
    def strategy_id(self) -> str:
        return self._strategy_id
    
    @property
    def version(self) -> str:
        return self._version
    
    def on_init(self, context: StrategyContext):
        self._init_called = True
    
    def on_tick(self, context: StrategyContext):
        self._tick_called_count += 1
        # Generate simple BUY intent
        return IntentProposal(
            strategy_id=self.strategy_id,
            symbol=context.symbol,
            side=SignalSide.BUY,
            signal_strength=0.8,
            reference_price=context.snapshot.mid_price,
            rationale=f"Mock signal from {self.strategy_id}"
        )
    
    def on_stop(self):
        self._stop_called = True


class CrashingStrategy(IStrategy):
    """Strategy that always raises exception in on_tick"""
    
    @property
    def strategy_id(self) -> str:
        return "crashing_strategy"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    def on_init(self, context: StrategyContext):
        pass
    
    def on_tick(self, context: StrategyContext):
        raise ValueError("Intentional crash for testing")
    
    def on_stop(self):
        pass


def test_strategy_sandboxing_exception_isolation():
    """Strategy exception is isolated and auto-disables only broken strategy"""
    cache = ThreadSafeSnapshotCache()
    registry = StrategyRegistry()
    engine = StrategyEngine(cache, registry)
    
    # Register normal and crashing strategies
    normal_strategy = MockStrategy("normal_strategy")
    crashing_strategy = CrashingStrategy()
    
    registry.register(normal_strategy, enabled=True)
    registry.register(crashing_strategy, enabled=True)
    
    # Add snapshot
    snapshot = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=50000.0,
        last_update_ms=int(time.time() * 1000),
        version=1
    )
    cache.update("BTC/USDT", snapshot)
    
    # Evaluate all
    proposals = engine.evaluate_all(["BTC/USDT"])
    
    # Normal strategy should generate proposal
    assert len(proposals) == 1
    assert proposals[0].strategy_id == "normal_strategy"
    
    # Crashing strategy should be auto-disabled
    assert "crashing_strategy" in engine.get_auto_disabled()
    assert not registry.is_enabled("crashing_strategy")
    
    # Normal strategy should still be enabled
    assert registry.is_enabled("normal_strategy")


def test_version_based_triggering():
    """Strategy is triggered only on new snapshot versions"""
    cache = ThreadSafeSnapshotCache()
    registry = StrategyRegistry()
    engine = StrategyEngine(cache, registry)
    
    strategy = MockStrategy("test_strategy")
    registry.register(strategy, enabled=True)
    
    # Version 1
    snapshot_v1 = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=50000.0,
        last_update_ms=int(time.time() * 1000),
        version=1
    )
    cache.update("BTC/USDT", snapshot_v1)
    
    # First evaluation (version 1)
    proposals1 = engine.evaluate_all(["BTC/USDT"])
    assert len(proposals1) == 1
    assert strategy._tick_called_count == 1
    
    # Second evaluation WITHOUT version change
    proposals2 = engine.evaluate_all(["BTC/USDT"])
    assert len(proposals2) == 0  # Skipped (version unchanged)
    assert strategy._tick_called_count == 1  # Not called again
    
    # Update to version 2
    snapshot_v2 = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=51000.0,
        last_update_ms=int(time.time() * 1000),
        version=2
    )
    cache.update("BTC/USDT", snapshot_v2)
    
    # Third evaluation WITH version change
    proposals3 = engine.evaluate_all(["BTC/USDT"])
    assert len(proposals3) == 1
    assert strategy._tick_called_count == 2  # Called again


def test_skip_on_stale_snapshot():
    """Evaluation skipped when snapshot is STALE"""
    cache = ThreadSafeSnapshotCache()
    registry = StrategyRegistry()
    engine = StrategyEngine(cache, registry)
    
    strategy = MockStrategy("test_strategy")
    registry.register(strategy, enabled=True)
    
    # STALE snapshot
    snapshot = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.STALE,
        mid_price=50000.0,
        last_update_ms=int(time.time() * 1000),
        version=1
    )
    cache.update("BTC/USDT", snapshot)
    
    # Evaluation should skip (STALE state)
    proposals = engine.evaluate_all(["BTC/USDT"])
    
    # No proposals generated
    assert len(proposals) == 0
    # Strategy not called because snapshot is STALE
    assert strategy._tick_called_count == 0


def test_skip_on_invalid_snapshot():
    """Evaluation skipped when snapshot is INVALID"""
    cache = ThreadSafeSnapshotCache()
    registry = StrategyRegistry()
    engine = StrategyEngine(cache, registry)
    
    strategy = MockStrategy("test_strategy")
    registry.register(strategy, enabled=True)
    
    # INVALID snapshot
    snapshot = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.INVALID,
        mid_price=50000.0,
        last_update_ms=int(time.time() * 1000),
        version=1
    )
    cache.update("BTC/USDT", snapshot)
    
    # Evaluation should skip
    proposals = engine.evaluate_all(["BTC/USDT"])
    
    assert len(proposals) == 0
    assert strategy._tick_called_count == 0


def test_deterministic_intent_output():
    """Strategy produces deterministic output for same input"""
    cache = ThreadSafeSnapshotCache()
    registry = StrategyRegistry()
    engine = StrategyEngine(cache, registry)
    
    strategy = MockStrategy("test_strategy")
    registry.register(strategy, enabled=True)
    
    snapshot = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=50000.0,
        last_update_ms=int(time.time() * 1000),
        version=1
    )
    cache.update("BTC/USDT", snapshot)
    
    # First evaluation
    proposals1 = engine.evaluate_all(["BTC/USDT"])
    
    # Reset version tracking to force re-evaluation
    engine.reset_version_tracking()
    
    # Second evaluation (same snapshot version)
    cache.update("BTC/USDT", snapshot)  # Re-publish same snapshot
    proposals2 = engine.evaluate_all(["BTC/USDT"])
    
    # Both should generate proposals
    assert len(proposals1) == 1
    assert len(proposals2) == 1
    
    # Proposals should have same strategy_id, symbol, side
    assert proposals1[0].strategy_id == proposals2[0].strategy_id
    assert proposals1[0].symbol == proposals2[0].symbol
    assert proposals1[0].side == proposals2[0].side


def test_zero_execution_leakage():
    """Strategy engine has no execution authority"""
    cache = ThreadSafeSnapshotCache()
    registry = StrategyRegistry()
    engine = StrategyEngine(cache, registry)
    
    # Verify engine has NO access to adapter/worker/queue
    assert not hasattr(engine, 'adapter')
    assert not hasattr(engine, 'worker')
    assert not hasattr(engine, 'queue')
    assert not hasattr(engine, 'submit_order')
    assert not hasattr(engine, 'execute')
    
    # Verify only passive outputs
    strategy = MockStrategy("test_strategy")
    registry.register(strategy, enabled=True)
    
    snapshot = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=50000.0,
        last_update_ms=int(time.time() * 1000),
        version=1
    )
    cache.update("BTC/USDT", snapshot)
    
    proposals = engine.evaluate_all(["BTC/USDT"])
    
    # Output is IntentProposal (passive)
    assert len(proposals) == 1
    assert isinstance(proposals[0], IntentProposal)


def test_registry_enable_disable():
    """Registry enable/disable affects strategy evaluation"""
    cache = ThreadSafeSnapshotCache()
    registry = StrategyRegistry()
    engine = StrategyEngine(cache, registry)
    
    strategy = MockStrategy("test_strategy")
    registry.register(strategy, enabled=True)
    
    snapshot = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=50000.0,
        last_update_ms=int(time.time() * 1000),
        version=1
    )
    cache.update("BTC/USDT", snapshot)
    
    # Evaluate while enabled
    proposals1 = engine.evaluate_all(["BTC/USDT"])
    assert len(proposals1) == 1
    
    # Disable strategy
    registry.disable("test_strategy")
    
    # Reset version tracking
    engine.reset_version_tracking()
    
    # Update snapshot version
    snapshot.version = 2
    cache.update("BTC/USDT", snapshot)
    
    # Evaluate while disabled
    proposals2 = engine.evaluate_all(["BTC/USDT"])
    assert len(proposals2) == 0  # No proposals (strategy disabled)


def test_strategy_initialization():
    """Engine initializes strategies with on_init"""
    cache = ThreadSafeSnapshotCache()
    registry = StrategyRegistry()
    engine = StrategyEngine(cache, registry)
    
    strategy = MockStrategy("test_strategy")
    registry.register(strategy, enabled=True)
    
    snapshot = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=50000.0,
        last_update_ms=int(time.time() * 1000),
        version=1
    )
    cache.update("BTC/USDT", snapshot)
    
    # Initialize
    engine.initialize_strategies(["BTC/USDT"])
    
    # on_init should have been called
    assert strategy._init_called is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
