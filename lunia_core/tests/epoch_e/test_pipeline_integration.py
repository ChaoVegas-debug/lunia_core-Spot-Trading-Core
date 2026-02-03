"""
EPOCH E Phase E1.1: Pipeline Integration Test
End-to-end cognition: MarketData → StrategyEngine → IntentProposal
"""
import pytest
import time

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.strategy.implementations.reference_midprice import ReferenceMidPriceThresholdStrategy
from app.services.strategy.registry import StrategyRegistry
from app.services.strategy.engine import StrategyEngine
from app.services.strategy.models import SignalSide

from app.services.market_data.realtime.synchronous import ThreadSafeSnapshotCache
from app.services.market_data.realtime.models import MarketSnapshot, SnapshotState


def test_pipeline_end_to_end():
    """
    End-to-end pipeline test: MarketData → Engine → Strategy → IntentProposal
    
    Scenario:
    1. Setup StrategyEngine with ThreadSafeSnapshotCache
    2. Register ReferenceMidPriceThresholdStrategy
    3. Inject snapshot V1 (price = 100)
    4. Inject snapshot V2 (price = 105)
    5. Verify:
       - Engine returns exactly one IntentProposal
       - Side = BUY
       - Rationale is correct
       - No execution side effects
    """
    # Setup
    cache = ThreadSafeSnapshotCache()
    registry = StrategyRegistry()
    engine = StrategyEngine(cache, registry)
    
    # Register reference strategy
    strategy = ReferenceMidPriceThresholdStrategy(threshold_pct=0.01)  # 1% threshold
    registry.register(strategy, enabled=True)
    
    # Inject snapshot V1 (price = 100)
    snapshot_v1 = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=100.0,
        last_update_ms=int(time.time() * 1000),
        version=1
    )
    cache.update("BTC/USDT", snapshot_v1)
    
    # First evaluation (initialize state)
    proposals_v1 = engine.evaluate_all(["BTC/USDT"])
    
    # No proposal on first tick (state initialization)
    assert len(proposals_v1) == 0
    
    # Verify state initialized
    assert strategy._last_mid_price == 100.0
    
    # Inject snapshot V2 (price = 105, +5% move)
    snapshot_v2 = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=105.0,
        last_update_ms=int(time.time() * 1000),
        version=2
    )
    cache.update("BTC/USDT", snapshot_v2)
    
    # Second evaluation (signal generation)
    proposals_v2 = engine.evaluate_all(["BTC/USDT"])
    
    # Verify EXACTLY ONE proposal
    assert len(proposals_v2) == 1
    
    proposal = proposals_v2[0]
    
    # Verify proposal properties
    assert proposal.strategy_id == "reference_midprice_v1"
    assert proposal.symbol == "BTC/USDT"
    assert proposal.side == SignalSide.BUY  # Upward move
    assert proposal.reference_price == 105.0
    assert proposal.signal_strength > 0.0
    
    # Verify rationale is explainable
    assert "5.0000%" in proposal.rationale or "5.00%" in proposal.rationale
    assert "1.00%" in proposal.rationale  # Threshold
    
    # Verify state updated
    assert strategy._last_mid_price == 105.0
    
    # Verify NO execution side effects
    assert not hasattr(engine, 'adapter')
    assert not hasattr(engine, 'submit_order')


def test_pipeline_multiple_symbols():
    """Pipeline handles multiple symbols independently"""
    cache = ThreadSafeSnapshotCache()
    registry = StrategyRegistry()
    engine = StrategyEngine(cache, registry)
    
    strategy = ReferenceMidPriceThresholdStrategy(threshold_pct=0.01)
    registry.register(strategy, enabled=True)
    
    # Initialize BTC
    snapshot_btc_v1 = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=100.0,
        last_update_ms=int(time.time() * 1000),
        version=1
    )
    cache.update("BTC/USDT", snapshot_btc_v1)
    
    # Initialize ETH
    snapshot_eth_v1 = MarketSnapshot(
        exchange="binance",
        symbol="ETH/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=50.0,
        last_update_ms=int(time.time() * 1000),
        version=1
    )
    cache.update("ETH/USDT", snapshot_eth_v1)
    
    # First evaluation (both initialize)
    proposals = engine.evaluate_all(["BTC/USDT", "ETH/USDT"])
    assert len(proposals) == 0
    
    # Update both (one above threshold, one below)
    snapshot_btc_v2 = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=105.0,  # +5% (above threshold)
        last_update_ms=int(time.time() * 1000),
        version=2
    )
    cache.update("BTC/USDT", snapshot_btc_v2)
    
    snapshot_eth_v2 = MarketSnapshot(
        exchange="binance",
        symbol="ETH/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=50.25,  # +0.5% (below threshold)
        last_update_ms=int(time.time() * 1000),
        version=2
    )
    cache.update("ETH/USDT", snapshot_eth_v2)
    
    # Second evaluation
    proposals = engine.evaluate_all(["BTC/USDT", "ETH/USDT"])
    
    # Only BTC proposal (ETH below threshold)
    assert len(proposals) == 1
    assert proposals[0].symbol == "BTC/USDT"


def test_pipeline_version_gating():
    """Pipeline respects version gating (no redundant evaluations)"""
    cache = ThreadSafeSnapshotCache()
    registry = StrategyRegistry()
    engine = StrategyEngine(cache, registry)
    
    strategy = ReferenceMidPriceThresholdStrategy(threshold_pct=0.01)
    registry.register(strategy, enabled=True)
    
    # V1
    snapshot_v1 = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=100.0,
        last_update_ms=int(time.time() * 1000),
        version=1
    )
    cache.update("BTC/USDT", snapshot_v1)
    engine.evaluate_all(["BTC/USDT"])
    
    # V2
    snapshot_v2 = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=105.0,
        last_update_ms=int(time.time() * 1000),
        version=2
    )
    cache.update("BTC/USDT", snapshot_v2)
    proposals1 = engine.evaluate_all(["BTC/USDT"])
    assert len(proposals1) == 1
    
    # Evaluate again WITHOUT version change
    proposals2 = engine.evaluate_all(["BTC/USDT"])
    
    # No proposals (version unchanged)
    assert len(proposals2) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
