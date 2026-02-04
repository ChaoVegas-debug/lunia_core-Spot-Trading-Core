"""
EPOCH E Phase E1: Strategy Isolation Tests
No shared state, independent lifecycle
"""
import pytest
import time

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lunia_core.app.services.strategy.interfaces import IStrategy
from lunia_core.app.services.strategy.models import StrategyContext, IntentProposal, SignalSide
from lunia_core.app.services.strategy.registry import StrategyRegistry
from lunia_core.app.services.strategy.engine import StrategyEngine

from lunia_core.app.services.market_data.realtime.synchronous import ThreadSafeSnapshotCache
from lunia_core.app.services.market_data.realtime.models import MarketSnapshot, SnapshotState


class StatefulStrategy(IStrategy):
    """Strategy with internal state (for isolation testing)"""
    
    def __init__(self, strategy_id: str):
        self._strategy_id = strategy_id
        self._counter = 0
    
    @property
    def strategy_id(self) -> str:
        return self._strategy_id
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    def on_init(self, context: StrategyContext):
        self._counter = 100  # Initialize with specific value
    
    def on_tick(self, context: StrategyContext):
        self._counter += 1
        return IntentProposal(
            strategy_id=self.strategy_id,
            symbol=context.symbol,
            side=SignalSide.BUY,
            signal_strength=self._counter / 1000.0,
            reference_price=context.snapshot.mid_price,
            rationale=f"Counter={self._counter}"
        )
    
    def on_stop(self):
        pass


def test_no_shared_state_between_strategies():
    """Strategies have independent state (no cross-contamination)"""
    cache = ThreadSafeSnapshotCache()
    registry = StrategyRegistry()
    engine = StrategyEngine(cache, registry)
    
    # Register two strategies with independent state
    strategy1 = StatefulStrategy("strategy_1")
    strategy2 = StatefulStrategy("strategy_2")
    
    registry.register(strategy1, enabled=True)
    registry.register(strategy2, enabled=True)
    
    # Initialize both
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
    
    engine.initialize_strategies(["BTC/USDT"])
    
    # Both should have independent counters
    assert strategy1._counter == 100
    assert strategy2._counter == 100
    
    # Evaluate (increments counters)
    proposals = engine.evaluate_all(["BTC/USDT"])
    
    # Both counters incremented independently
    assert strategy1._counter == 101
    assert strategy2._counter == 101
    
    # Update snapshot
    snapshot.version = 2
    cache.update("BTC/USDT", snapshot)
    
    # Evaluate again
    proposals = engine.evaluate_all(["BTC/USDT"])
    
    # Counters still independent
    assert strategy1._counter == 102
    assert strategy2._counter == 102


def test_disabling_one_strategy_does_not_affect_others():
    """Disabling one strategy leaves others running"""
    cache = ThreadSafeSnapshotCache()
    registry = StrategyRegistry()
    engine = StrategyEngine(cache, registry)
    
    strategy1 = StatefulStrategy("strategy_1")
    strategy2 = StatefulStrategy("strategy_2")
    
    registry.register(strategy1, enabled=True)
    registry.register(strategy2, enabled=True)
    
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
    
    # Evaluate both
    proposals1 = engine.evaluate_all(["BTC/USDT"])
    assert len(proposals1) == 2  # Both strategies
    
    # Disable strategy1
    registry.disable("strategy_1")
    
    # Update snapshot
    snapshot.version = 2
    cache.update("BTC/USDT", snapshot)
    
    # Evaluate again
    proposals2 = engine.evaluate_all(["BTC/USDT"])
    
    # Only strategy2 should generate proposal
    assert len(proposals2) == 1
    assert proposals2[0].strategy_id == "strategy_2"


def test_registry_isolation_unregister():
    """Unregistering one strategy doesn't affect others"""
    registry = StrategyRegistry()
    
    strategy1 = StatefulStrategy("strategy_1")
    strategy2 = StatefulStrategy("strategy_2")
    
    registry.register(strategy1, enabled=True)
    registry.register(strategy2, enabled=True)
    
    assert len(registry.get_all_strategies()) == 2
    
    # Unregister strategy1
    registry.unregister("strategy_1")
    
    # strategy2 should still be registered
    assert len(registry.get_all_strategies()) == 1
    assert registry.get_strategy("strategy_2") is not None
    assert registry.is_enabled("strategy_2")


def test_strategy_lifecycle_on_stop_called():
    """on_stop called on unregister and shutdown"""
    registry = StrategyRegistry()
    
    class TrackingStrategy(IStrategy):
        def __init__(self):
            self.stop_called = False
        
        @property
        def strategy_id(self) -> str:
            return "tracking"
        
        @property
        def version(self) -> str:
            return "1.0.0"
        
        def on_init(self, context: StrategyContext):
            pass
        
        def on_tick(self, context: StrategyContext):
            return None
        
        def on_stop(self):
            self.stop_called = True
    
    strategy = TrackingStrategy()
    registry.register(strategy, enabled=True)
    
    # Unregister should call on_stop
    registry.unregister("tracking")
    
    assert strategy.stop_called is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
