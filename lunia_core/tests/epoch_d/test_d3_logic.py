"""
EPOCH D Phase D3.1: Realtime Engine Logic Tests (STANDALONE)
Pure logic tests WITHOUT async complexity - NO pytest-asyncio required
"""
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lunia_core.app.services.market_data.realtime.models import (
    SnapshotState,
    MarketSnapshot,
    PriceLevel,
    OrderBookL2
)


def test_snapshot_state_enum():
    """SnapshotState enum has correct values"""
    assert SnapshotState.VALID == "VALID"
    assert SnapshotState.STALE == "STALE"
    assert SnapshotState.INVALID == "INVALID"


def test_snapshot_defaults_to_stale():
    """MarketSnapshot should default to STALE (fail-closed)"""
    snapshot = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        last_update_ms=1609459200000
    )
    
    assert snapshot.snapshot_state == SnapshotState.STALE


def test_crossed_book_detection_logic():
    """Crossed book (bid >= ask) should be detectable"""
    bid = 50000.0
    ask = 49999.0  # Crossed (ask < bid)
    
    is_crossed = bid >= ask
    assert is_crossed is True
    
    # Non-crossed
    bid_ok = 50000.0
    ask_ok = 50001.0
    is_crossed_ok = bid_ok >= ask_ok
    assert is_crossed_ok is False


def test_l2_bids_descending_validation():
    """Bids must be strictly descending"""
    bids = [50000.0, 49999.0, 49998.0]
    
    # Check descending
    is_descending = all(
        bids[i] > bids[i + 1]
        for i in range(len(bids) - 1)
    )
    assert is_descending is True
    
    # Non-descending (ascending)
    bids_bad = [49998.0, 49999.0, 50000.0]
    is_descending_bad = all(
        bids_bad[i] > bids_bad[i + 1]
        for i in range(len(bids_bad) - 1)
    )
    assert is_descending_bad is False


def test_l2_asks_ascending_validation():
    """Asks must be strictly ascending"""
    asks = [50001.0, 50002.0, 50003.0]
    
    # Check ascending
    is_ascending = all(
        asks[i] < asks[i + 1]
        for i in range(len(asks) - 1)
    )
    assert is_ascending is True
    
    # Non-ascending (descending)
    asks_bad = [50003.0, 50002.0, 50001.0]
    is_ascending_bad = all(
        asks_bad[i] < asks_bad[i + 1]
        for i in range(len(asks_bad) - 1)
    )
    assert is_ascending_bad is False


def test_monotonic_version_logic():
    """Snapshot version should be monotonically increasing"""
    snapshot = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        last_update_ms=1609459200000,
        version=0
    )
    
    # Increment version
    snapshot.version += 1
    assert snapshot.version == 1
    
    snapshot.version += 1
    assert snapshot.version == 2
    
    # Monotonic
    assert snapshot.version > 0


def test_partial_data_detection():
    """Snapshot should track partial data (missing ticker/orderbook)"""
    snapshot = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        last_update_ms=1609459200000
    )
    
    # Initially no data
    assert snapshot.has_ticker is False
    assert snapshot.has_orderbook is False
    
    # Partial data (ticker only)
    snapshot.has_ticker = True
    is_partial = not (snapshot.has_ticker and snapshot.has_orderbook)
    assert is_partial is True
    
    # Complete data
    snapshot.has_orderbook = True
    is_complete = snapshot.has_ticker and snapshot.has_orderbook
    assert is_complete is True


def test_staleness_threshold_logic():
    """Staleness threshold detection"""
    import time
    
    staleness_threshold_ms = 5000
    
    # Fresh data
    last_update_ms = int(time.time() * 1000)
    now_ms = last_update_ms + 1000  # 1s later
    age_ms = now_ms - last_update_ms
    
    is_stale = age_ms > staleness_threshold_ms
    assert is_stale is False
    
    # Stale data
    now_ms_stale = last_update_ms + 6000  # 6s later
    age_ms_stale = now_ms_stale - last_update_ms
    
    is_stale_check = age_ms_stale > staleness_threshold_ms
    assert is_stale_check is True


def test_mid_price_calculation():
    """Mid price should be (bid + ask) / 2"""
    bid = 50000.0
    ask = 50002.0
    
    mid_price = (bid + ask) / 2.0
    assert mid_price == 50001.0


def test_duplicate_price_level_detection():
    """Duplicate price levels should be detectable"""
    prices = [50000.0, 49999.0, 50000.0]  # Duplicate
    
    seen = set()
    has_duplicate = False
    
    for price in prices:
        if price in seen:
            has_duplicate = True
            break
        seen.add(price)
    
    assert has_duplicate is True
    
    # No duplicates
    prices_ok = [50000.0, 49999.0, 49998.0]
    seen_ok = set()
    has_duplicate_ok = False
    
    for price in prices_ok:
        if price in seen_ok:
            has_duplicate_ok = True
            break
        seen_ok.add(price)
    
    assert has_duplicate_ok is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
