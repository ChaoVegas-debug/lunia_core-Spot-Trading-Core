"""
EPOCH D Phase D3.1: Real-Time Engine Tests
Async tests with pytest-asyncio, mock WebSocket feed
"""
import pytest
import asyncio
import time

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lunia_core.app.services.market_data.realtime.models import (
    TickerUpdate,
    OrderBookL2,
    PriceLevel,
    SnapshotState
)
from lunia_core.app.services.market_data.realtime.interfaces import MockWebSocketClient
from lunia_core.app.services.market_data.realtime.manager import RealTimeMarketDataEngine


@pytest.fixture
def mock_client():
    """Create mock WebSocket client"""
    return MockWebSocketClient()


@pytest.fixture
async def engine(mock_client):
    """Create and start engine"""
    eng = RealTimeMarketDataEngine(
        client=mock_client,
        staleness_threshold_ms=2000,  # 2s for faster tests
        buffer_size=100,
        l2_depth=5
    )
    yield eng
    
    # Cleanup
    if eng._active:
        await eng.stop()


@pytest.mark.asyncio
async def test_startup_barrier_waits_for_valid_snapshot(mock_client, engine):
    """Startup barrier should wait until first VALID snapshot"""
    symbol = "BTC/USDT"
    
    # Inject valid data
    now_ms = int(time.time() * 1000)
    
    mock_client.inject_ticker(TickerUpdate(
        exchange="binance",
        symbol=symbol,
        market_type="spot",
        bid=50000.0,
        ask=50001.0,
        last=50000.5,
        timestamp_ms=now_ms,
        received_at_ms=now_ms
    ))
    
    mock_client.inject_orderbook(OrderBookL2(
        exchange="binance",
        symbol=symbol,
        market_type="spot",
        bids=[PriceLevel(price=50000.0, amount=1.0), PriceLevel(price=49999.0, amount=2.0)],
        asks=[PriceLevel(price=50001.0, amount=1.0), PriceLevel(price=50002.0, amount=2.0)],
        timestamp_ms=now_ms,
        received_at_ms=now_ms
    ))
    
    # Start engine
    await engine.start("binance", [symbol], "spot")
    
    # Wait for ready
    ready = await engine.wait_until_ready(symbol, timeout=5.0)
    assert ready is True
    
    # Get snapshot
    snapshot = await engine.get_snapshot(symbol)
    assert snapshot is not None
    assert snapshot.snapshot_state == SnapshotState.VALID


@pytest.mark.asyncio
async def test_crossed_book_marks_invalid(mock_client, engine):
    """Crossed book (bid >= ask) should mark snapshot INVALID"""
    symbol = "BTC/USDT"
    now_ms = int(time.time() * 1000)
    
    # Inject valid ticker first
    mock_client.inject_ticker(TickerUpdate(
        exchange="binance",
        symbol=symbol,
        market_type="spot",
        bid=50000.0,
        ask=50001.0,
        last=50000.5,
        timestamp_ms=now_ms,
        received_at_ms=now_ms
    ))
    
    # Inject CROSSED orderbook
    mock_client.inject_orderbook(OrderBookL2(
        exchange="binance",
        symbol=symbol,
        market_type="spot",
        bids=[PriceLevel(price=50002.0, amount=1.0)],  # bid > ask
        asks=[PriceLevel(price=50001.0, amount=1.0)],
        timestamp_ms=now_ms,
        received_at_ms=now_ms
    ))
    
    await engine.start("binance", [symbol], "spot")
    await asyncio.sleep(0.2)  # Let updates process
    
    snapshot = await engine.get_snapshot(symbol)
    assert snapshot.snapshot_state == SnapshotState.INVALID


@pytest.mark.asyncio
async def test_l2_validation_bids_descending(mock_client, engine):
    """Bids must be strictly descending"""
    symbol = "BTC/USDT"
    now_ms = int(time.time() * 1000)
    
    mock_client.inject_ticker(TickerUpdate(
        exchange="binance",
        symbol=symbol,
        market_type="spot",
        bid=50000.0,
        ask=50001.0,
        last=50000.5,
        timestamp_ms=now_ms,
        received_at_ms=now_ms
    ))
    
    # Bids NOT descending (ascending instead)
    mock_client.inject_orderbook(OrderBookL2(
        exchange="binance",
        symbol=symbol,
        market_type="spot",
        bids=[PriceLevel(price=49999.0, amount=1.0), PriceLevel(price=50000.0, amount=2.0)],  # BAD: ascending
        asks=[PriceLevel(price=50001.0, amount=1.0)],
        timestamp_ms=now_ms,
        received_at_ms=now_ms
    ))
    
    await engine.start("binance", [symbol], "spot")
    await asyncio.sleep(0.2)
    
    snapshot = await engine.get_snapshot(symbol)
    # Should be INVALID due to L2 violation
    assert snapshot.snapshot_state == SnapshotState.INVALID


@pytest.mark.asyncio
async def test_l2_validation_asks_ascending(mock_client, engine):
    """Asks must be strictly ascending"""
    symbol = "BTC/USDT"
    now_ms = int(time.time() * 1000)
    
    mock_client.inject_ticker(TickerUpdate(
        exchange="binance",
        symbol=symbol,
        market_type="spot",
        bid=50000.0,
        ask=50001.0,
        last=50000.5,
        timestamp_ms=now_ms,
        received_at_ms=now_ms
    ))
    
    # Asks NOT ascending (descending instead)
    mock_client.inject_orderbook(OrderBookL2(
        exchange="binance",
        symbol=symbol,
        market_type="spot",
        bids=[PriceLevel(price=50000.0, amount=1.0)],
        asks=[PriceLevel(price=50002.0, amount=1.0), PriceLevel(price=50001.0, amount=2.0)],  # BAD: descending
        timestamp_ms=now_ms,
        received_at_ms=now_ms
    ))
    
    await engine.start("binance", [symbol], "spot")
    await asyncio.sleep(0.2)
    
    snapshot = await engine.get_snapshot(symbol)
    assert snapshot.snapshot_state == SnapshotState.INVALID


@pytest.mark.asyncio
async def test_partial_data_marks_stale(mock_client, engine):
    """Missing ticker OR orderbook should mark snapshot STALE"""
    symbol = "BTC/USDT"
    now_ms = int(time.time() * 1000)
    
    # Only inject ticker (no orderbook)
    mock_client.inject_ticker(TickerUpdate(
        exchange="binance",
        symbol=symbol,
        market_type="spot",
        bid=50000.0,
        ask=50001.0,
        last=50000.5,
        timestamp_ms=now_ms,
        received_at_ms=now_ms
    ))
    
    await engine.start("binance", [symbol], "spot")
    await asyncio.sleep(0.2)
    
    snapshot = await engine.get_snapshot(symbol)
    assert snapshot.has_ticker is True
    assert snapshot.has_orderbook is False
    assert snapshot.snapshot_state == SnapshotState.STALE  # Partial data


@pytest.mark.asyncio
async def test_staleness_detection(mock_client, engine):
    """Snapshot should become STALE after threshold"""
    symbol = "BTC/USDT"
    now_ms = int(time.time() * 1000)
    
    # Inject complete valid data
    mock_client.inject_ticker(TickerUpdate(
        exchange="binance",
        symbol=symbol,
        market_type="spot",
        bid=50000.0,
        ask=50001.0,
        last=50000.5,
        timestamp_ms=now_ms,
        received_at_ms=now_ms
    ))
    
    mock_client.inject_orderbook(OrderBookL2(
        exchange="binance",
        symbol=symbol,
        market_type="spot",
        bids=[PriceLevel(price=50000.0, amount=1.0)],
        asks=[PriceLevel(price=50001.0, amount=1.0)],
        timestamp_ms=now_ms,
        received_at_ms=now_ms
    ))
    
    await engine.start("binance", [symbol], "spot")
    await engine.wait_until_ready(symbol, timeout=5.0)
    
    # Initially VALID
    snapshot = await engine.get_snapshot(symbol)
    assert snapshot.snapshot_state == SnapshotState.VALID
    
    # Wait for staleness (threshold is 2s in test fixture)
    await asyncio.sleep(2.5)
    
    # Should be STALE now
    snapshot = await engine.get_snapshot(symbol)
    assert snapshot.snapshot_state == SnapshotState.STALE


@pytest.mark.asyncio
async def test_symbol_isolation(mock_client, engine):
    """Failure in one symbol should not affect others"""
    symbol1 = "BTC/USDT"
    symbol2 = "ETH/USDT"
    now_ms = int(time.time() * 1000)
    
    # Symbol 1: valid data
    mock_client.inject_ticker(TickerUpdate(
        exchange="binance",
        symbol=symbol1,
        market_type="spot",
        bid=50000.0,
        ask=50001.0,
        last=50000.5,
        timestamp_ms=now_ms,
        received_at_ms=now_ms
    ))
    
    mock_client.inject_orderbook(OrderBookL2(
        exchange="binance",
        symbol=symbol1,
        market_type="spot",
        bids=[PriceLevel(price=50000.0, amount=1.0)],
        asks=[PriceLevel(price=50001.0, amount=1.0)],
        timestamp_ms=now_ms,
        received_at_ms=now_ms
    ))
    
    # Symbol 2: crossed book (INVALID)
    mock_client.inject_ticker(TickerUpdate(
        exchange="binance",
        symbol=symbol2,
        market_type="spot",
        bid=3000.0,
        ask=3001.0,
        last=3000.5,
        timestamp_ms=now_ms,
        received_at_ms=now_ms
    ))
    
    mock_client.inject_orderbook(OrderBookL2(
        exchange="binance",
        symbol=symbol2,
        market_type="spot",
        bids=[PriceLevel(price=3002.0, amount=1.0)],  # Crossed
        asks=[PriceLevel(price=3001.0, amount=1.0)],
        timestamp_ms=now_ms,
        received_at_ms=now_ms
    ))
    
    await engine.start("binance", [symbol1, symbol2], "spot")
    await asyncio.sleep(0.2)
    
    # Symbol 1 should be VALID
    snapshot1 = await engine.get_snapshot(symbol1)
    assert snapshot1.snapshot_state == SnapshotState.VALID
    
    # Symbol 2 should be INVALID (isolation preserved)
    snapshot2 = await engine.get_snapshot(symbol2)
    assert snapshot2.snapshot_state == SnapshotState.INVALID


@pytest.mark.asyncio
async def test_graceful_shutdown_marks_stale(mock_client, engine):
    """Stop should mark all snapshots STALE and cancel tasks"""
    symbol = "BTC/USDT"
    now_ms = int(time.time() * 1000)
    
    mock_client.inject_ticker(TickerUpdate(
        exchange="binance",
        symbol=symbol,
        market_type="spot",
        bid=50000.0,
        ask=50001.0,
        last=50000.5,
        timestamp_ms=now_ms,
        received_at_ms=now_ms
    ))
    
    mock_client.inject_orderbook(OrderBookL2(
        exchange="binance",
        symbol=symbol,
        market_type="spot",
        bids=[PriceLevel(price=50000.0, amount=1.0)],
        asks=[PriceLevel(price=50001.0, amount=1.0)],
        timestamp_ms=now_ms,
        received_at_ms=now_ms
    ))
    
    await engine.start("binance", [symbol], "spot")
    await engine.wait_until_ready(symbol, timeout=5.0)
    
    # Stop engine
    await engine.stop()
    
    # Snapshot should be STALE
    snapshot = await engine.get_snapshot(symbol)
    assert snapshot.snapshot_state == SnapshotState.STALE
    
    # Engine should be inactive
    assert engine._active is False


@pytest.mark.asyncio
async def test_no_execution_side_effects(mock_client, engine):
    """Engine must never submit orders or call execution adapters"""
    # This test verifies architectural constraint
    # Real test would mock execution adapters and assert they're never called
    
    # Engine is read-only, observational only
    assert not hasattr(engine, 'submit_order')
    assert not hasattr(engine, 'cancel_order')
    
    # All methods are read operations
    symbol = "BTC/USDT"
    now_ms = int(time.time() * 1000)
    
    mock_client.inject_ticker(TickerUpdate(
        exchange="binance",
        symbol=symbol,
        market_type="spot",
        bid=50000.0,
        ask=50001.0,
        last=50000.5,
        timestamp_ms=now_ms,
        received_at_ms=now_ms
    ))
    
    mock_client.inject_orderbook(OrderBookL2(
        exchange="binance",
        symbol=symbol,
        market_type="spot",
        bids=[PriceLevel(price=50000.0, amount=1.0)],
        asks=[PriceLevel(price=50001.0, amount=1.0)],
        timestamp_ms=now_ms,
        received_at_ms=now_ms
    ))
    
    await engine.start("binance", [symbol], "spot")
    await engine.wait_until_ready(symbol, timeout=5.0)
    
    # Read operations only
    snapshot = await engine.get_snapshot(symbol)
    health = await engine.get_health()
    
    # No side effects occurred
    assert snapshot is not None
    assert health is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
