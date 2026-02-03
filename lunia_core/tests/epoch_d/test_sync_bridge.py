"""
EPOCH D Phase D3.2.1: Sync Bridge Tests
Thread-safe cache concurrency and atomicity tests
"""
import pytest
import threading
import time

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.market_data.realtime.synchronous import ThreadSafeSnapshotCache
from app.services.market_data.realtime.models import MarketSnapshot, SnapshotState, PriceLevel


def test_cache_update_and_get():
    """ThreadSafeSnapshotCache basic update and get"""
    cache = ThreadSafeSnapshotCache()
    
    snapshot = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        bid=50000.0,
        ask=50001.0,
        mid_price=50000.5,
        last_update_ms=int(time.time() * 1000),
        version=1
    )
    
    cache.update("BTC/USDT", snapshot)
    
    retrieved = cache.get("BTC/USDT")
    
    assert retrieved is not None
    assert retrieved.symbol == "BTC/USDT"
    assert retrieved.bid == 50000.0
    assert retrieved.snapshot_state == SnapshotState.VALID


def test_cache_missing_symbol_returns_none():
    """Missing symbol returns None (fail-closed)"""
    cache = ThreadSafeSnapshotCache()
    
    result = cache.get("UNKNOWN/PAIR")
    
    assert result is None


def test_cache_deep_copy_isolation():
    """Cache returns deep copies (no shared mutation)"""
    cache = ThreadSafeSnapshotCache()
    
    snapshot = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        bid=50000.0,
        last_update_ms=int(time.time() * 1000),
        version=1
    )
    
    cache.update("BTC/USDT", snapshot)
    
    # Get first copy
    copy1 = cache.get("BTC/USDT")
    
    # Mutate copy1
    copy1.bid = 99999.0
    
    # Get second copy
    copy2 = cache.get("BTC/USDT")
    
    # copy2 should NOT see copy1's mutation
    assert copy2.bid == 50000.0
    assert copy1.bid == 99999.0


def test_cache_concurrent_writer_reader():
    """Concurrent writer and reader threads"""
    cache = ThreadSafeSnapshotCache()
    results = []
    errors = []
    
    def writer():
        try:
            for i in range(100):
                snapshot = MarketSnapshot(
                    exchange="binance",
                    symbol="BTC/USDT",
                    market_type="spot",
                    snapshot_state=SnapshotState.VALID,
                    bid=50000.0 + i,
                    last_update_ms=int(time.time() * 1000),
                    version=i
                )
                cache.update("BTC/USDT", snapshot)
                time.sleep(0.001)  # Simulate work
        except Exception as e:
            errors.append(("writer", e))
    
    def reader():
        try:
            for _ in range(100):
                snapshot = cache.get("BTC/USDT")
                if snapshot:
                    results.append(snapshot.version)
                time.sleep(0.001)
        except Exception as e:
            errors.append(("reader", e))
    
    writer_thread = threading.Thread(target=writer)
    reader_thread = threading.Thread(target=reader)
    
    writer_thread.start()
    reader_thread.start()
    
    writer_thread.join()
    reader_thread.join()
    
    # No errors
    assert len(errors) == 0
    
    # Reader saw some updates
    assert len(results) > 0


def test_cache_no_partial_reads():
    """No torn reads (atomic visibility)"""
    cache = ThreadSafeSnapshotCache()
    errors = []
    
    def writer():
        try:
            for i in range(50):
                snapshot = MarketSnapshot(
                    exchange="binance",
                    symbol="BTC/USDT",
                    market_type="spot",
                    snapshot_state=SnapshotState.VALID,
                    bid=float(i),
                    ask=float(i) + 1.0,  # ask = bid + 1
                    last_update_ms=int(time.time() * 1000),
                    version=i
                )
                cache.update("BTC/USDT", snapshot)
        except Exception as e:
            errors.append(("writer", e))
    
    def reader():
        try:
            for _ in range(50):
                snapshot = cache.get("BTC/USDT")
                if snapshot and snapshot.bid is not None and snapshot.ask is not None:
                    # Invariant: ask should ALWAYS be bid + 1
                    if snapshot.ask != snapshot.bid + 1.0:
                        errors.append(("reader", f"Torn read: bid={snapshot.bid}, ask={snapshot.ask}"))
        except Exception as e:
            errors.append(("reader", e))
    
    writer_thread = threading.Thread(target=writer)
    reader_thread = threading.Thread(target=reader)
    
    writer_thread.start()
    reader_thread.start()
    
    writer_thread.join()
    reader_thread.join()
    
    # No torn reads detected
    assert len(errors) == 0


def test_cache_get_all_symbols():
    """get_all_symbols returns tracked symbols"""
    cache = ThreadSafeSnapshotCache()
    
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    
    for symbol in symbols:
        snapshot = MarketSnapshot(
            exchange="binance",
            symbol=symbol,
            market_type="spot",
            snapshot_state=SnapshotState.VALID,
            last_update_ms=int(time.time() * 1000)
        )
        cache.update(symbol, snapshot)
    
    tracked = cache.get_all_symbols()
    
    assert set(tracked) == set(symbols)


def test_cache_clear():
    """clear() removes all snapshots"""
    cache = ThreadSafeSnapshotCache()
    
    snapshot = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        last_update_ms=int(time.time() * 1000)
    )
    
    cache.update("BTC/USDT", snapshot)
    assert cache.get("BTC/USDT") is not None
    
    cache.clear()
    assert cache.get("BTC/USDT") is None
    assert cache.get_all_symbols() == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
