"""
EPOCH E Phase E1.1: Reference Strategy Unit Tests
"""
import pytest
import time

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lunia_core.app.services.strategy.implementations.reference_midprice import ReferenceMidPriceThresholdStrategy
from lunia_core.app.services.strategy.models import StrategyContext, SignalSide

from lunia_core.app.services.market_data.realtime.models import MarketSnapshot, SnapshotState


def test_first_tick_returns_none():
    """First tick always returns None (initializes state)"""
    strategy = ReferenceMidPriceThresholdStrategy(threshold_pct=0.001)
    
    snapshot = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=50000.0,
        last_update_ms=int(time.time() * 1000),
        version=1
    )
    
    context = StrategyContext(
        symbol="BTC/USDT",
        snapshot=snapshot,
        snapshot_version=1,
        received_at_ms=int(time.time() * 1000)
    )
    
    proposal = strategy.on_tick(context)
    
    # First tick returns None
    assert proposal is None
    
    # State should be initialized
    assert strategy._last_mid_price == 50000.0


def test_state_persistence():
    """State persists correctly across ticks"""
    strategy = ReferenceMidPriceThresholdStrategy(threshold_pct=0.001)
    
    # First tick (price = 100)
    snapshot1 = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=100.0,
        last_update_ms=int(time.time() * 1000),
        version=1
    )
    context1 = StrategyContext(
        symbol="BTC/USDT",
        snapshot=snapshot1,
        snapshot_version=1,
        received_at_ms=int(time.time() * 1000)
    )
    strategy.on_tick(context1)
    assert strategy._last_mid_price == 100.0
    
    # Second tick (price = 100.05, below threshold)
    snapshot2 = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=100.05,
        last_update_ms=int(time.time() * 1000),
        version=2
    )
    context2 = StrategyContext(
        symbol="BTC/USDT",
        snapshot=snapshot2,
        snapshot_version=2,
        received_at_ms=int(time.time() * 1000)
    )
    proposal = strategy.on_tick(context2)
    
    # No proposal (delta = 0.05%)
    assert proposal is None
    
    # State updated to new price
    assert strategy._last_mid_price == 100.05


def test_upward_move_proposes_buy():
    """Upward price move above threshold proposes BUY"""
    strategy = ReferenceMidPriceThresholdStrategy(threshold_pct=0.001)  # 0.10%
    
    # First tick (initialize)
    snapshot1 = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=100.0,
        last_update_ms=int(time.time() * 1000),
        version=1
    )
    context1 = StrategyContext(
        symbol="BTC/USDT",
        snapshot=snapshot1,
        snapshot_version=1,
        received_at_ms=int(time.time() * 1000)
    )
    strategy.on_tick(context1)
    
    # Second tick (price up 0.15%, above threshold)
    snapshot2 = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=100.15,
        last_update_ms=int(time.time() * 1000),
        version=2
    )
    context2 = StrategyContext(
        symbol="BTC/USDT",
        snapshot=snapshot2,
        snapshot_version=2,
        received_at_ms=int(time.time() * 1000)
    )
    proposal = strategy.on_tick(context2)
    
    # BUY proposal generated
    assert proposal is not None
    assert proposal.side == SignalSide.BUY
    assert proposal.symbol == "BTC/USDT"
    assert proposal.reference_price == 100.15
    assert "0.15" in proposal.rationale or "0.1500" in proposal.rationale
    
    # State updated
    assert strategy._last_mid_price == 100.15


def test_downward_move_proposes_sell():
    """Downward price move below threshold proposes SELL"""
    strategy = ReferenceMidPriceThresholdStrategy(threshold_pct=0.001)  # 0.10%
    
    # First tick (initialize)
    snapshot1 = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=100.0,
        last_update_ms=int(time.time() * 1000),
        version=1
    )
    context1 = StrategyContext(
        symbol="BTC/USDT",
        snapshot=snapshot1,
        snapshot_version=1,
        received_at_ms=int(time.time() * 1000)
    )
    strategy.on_tick(context1)
    
    # Second tick (price down 0.20%, below -threshold)
    snapshot2 = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=99.80,
        last_update_ms=int(time.time() * 1000),
        version=2
    )
    context2 = StrategyContext(
        symbol="BTC/USDT",
        snapshot=snapshot2,
        snapshot_version=2,
        received_at_ms=int(time.time() * 1000)
    )
    proposal = strategy.on_tick(context2)
    
    # SELL proposal generated
    assert proposal is not None
    assert proposal.side == SignalSide.SELL
    assert proposal.symbol == "BTC/USDT"
    assert proposal.reference_price == 99.80
    assert "-0.20" in proposal.rationale or "-0.2000" in proposal.rationale
    
    # State updated
    assert strategy._last_mid_price == 99.80


def test_determinism():
    """Same input produces same output (determinism)"""
    strategy1 = ReferenceMidPriceThresholdStrategy(threshold_pct=0.001)
    strategy2 = ReferenceMidPriceThresholdStrategy(threshold_pct=0.001)
    
    # Same sequence of snapshots
    snapshots = [
        MarketSnapshot(
            exchange="binance",
            symbol="BTC/USDT",
            market_type="spot",
            snapshot_state=SnapshotState.VALID,
            mid_price=100.0,
            last_update_ms=int(time.time() * 1000),
            version=1
        ),
        MarketSnapshot(
            exchange="binance",
            symbol="BTC/USDT",
            market_type="spot",
            snapshot_state=SnapshotState.VALID,
            mid_price=100.15,
            last_update_ms=int(time.time() * 1000),
            version=2
        ),
    ]
    
    proposals1 = []
    proposals2 = []
    
    for i, snapshot in enumerate(snapshots):
        context = StrategyContext(
            symbol="BTC/USDT",
            snapshot=snapshot,
            snapshot_version=i + 1,
            received_at_ms=int(time.time() * 1000)
        )
        
        p1 = strategy1.on_tick(context)
        p2 = strategy2.on_tick(context)
        
        proposals1.append(p1)
        proposals2.append(p2)
    
    # Same outputs
    assert len(proposals1) == len(proposals2)
    for p1, p2 in zip(proposals1, proposals2):
        if p1 is None:
            assert p2 is None
        else:
            assert p1.side == p2.side
            assert p1.symbol == p2.symbol
            assert p1.reference_price == p2.reference_price


def test_no_execution_leakage():
    """Strategy has no execution authority"""
    strategy = ReferenceMidPriceThresholdStrategy()
    
    # Verify NO execution attributes
    assert not hasattr(strategy, 'adapter')
    assert not hasattr(strategy, 'worker')
    assert not hasattr(strategy, 'queue')
    assert not hasattr(strategy, 'submit_order')
    assert not hasattr(strategy, 'execute')


def test_fail_silent_on_missing_mid_price():
    """Strategy returns None when mid_price is missing"""
    strategy = ReferenceMidPriceThresholdStrategy()
    
    snapshot = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=None,  # Missing
        last_update_ms=int(time.time() * 1000),
        version=1
    )
    context = StrategyContext(
        symbol="BTC/USDT",
        snapshot=snapshot,
        snapshot_version=1,
        received_at_ms=int(time.time() * 1000)
    )
    
    proposal = strategy.on_tick(context)
    
    # Fail-silent
    assert proposal is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
