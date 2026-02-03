"""
EPOCH D Phase D3.2: Worker-MarketData Integration Tests
Tests proving execution blocks on STALE/INVALID snapshots and price deviations
"""
import pytest
from unittest.mock import Mock, MagicMock
import time

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.market_data.realtime.models import (
    MarketSnapshot,
    SnapshotState,
    PriceLevel
)
from app.services.execution.price_guard import PriceSanityGuard, GuardResult


def test_price_guard_blocks_snapshot_stale():
    """Price guard blocks when snapshot state is STALE"""
    guard = PriceSanityGuard(band_pct=5.0)
    
    snapshot = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.STALE,  # Not VALID
        last_update_ms=int(time.time() * 1000)
    )
    
    order = {
        "symbol": "BTC/USDT",
        "side": "BUY",
        "order_style": "LIMIT",
        "price": 50000.0,
        "quantity": 0.1
    }
    
    result = guard.validate(order, snapshot)
    
    assert result.passed is False
    assert result.reason_code == "EXECUTION_BLOCKED_MD_NOT_VALID"
    assert "snapshot_state" in result.details
    assert result.details["snapshot_state"] == "STALE"


def test_price_guard_blocks_snapshot_invalid():
    """Price guard blocks when snapshot state is INVALID"""
    guard = PriceSanityGuard(band_pct=5.0)
    
    snapshot = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.INVALID,  # Crossed or corrupted
        last_update_ms=int(time.time() * 1000)
    )
    
    order = {
        "symbol": "BTC/USDT",
        "side": "BUY",
        "order_style": "LIMIT",
        "price": 50000.0,
        "quantity": 0.1
    }
    
    result = guard.validate(order, snapshot)
    
    assert result.passed is False
    assert result.reason_code == "EXECUTION_BLOCKED_MD_CROSSED_OR_INVALID"


def test_price_guard_blocks_limit_order_price_deviation():
    """Price guard blocks limit order with excessive price deviation"""
    guard = PriceSanityGuard(band_pct=5.0)
    
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
    
    # Order price deviates by 10% (> 5% band)
    order = {
        "symbol": "BTC/USDT",
        "side": "BUY",
        "order_style": "LIMIT",
        "price": 55000.0,  # 10% deviation
        "quantity": 0.1
    }
    
    result = guard.validate(order, snapshot)
    
    assert result.passed is False
    assert result.reason_code == "EXECUTION_BLOCKED_PRICE_BAND"
    assert "deviation_pct" in result.details
    assert result.details["deviation_pct"] > 5.0
    assert "mid_price" in result.details
    assert "order_price" in result.details


def test_price_guard_allows_limit_order_within_band():
    """Price guard allows limit order within configured band"""
    guard = PriceSanityGuard(band_pct=5.0)
    
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
    
    # Order price within 5% band
    order = {
        "symbol": "BTC/USDT",
        "side": "BUY",
        "order_style": "LIMIT",
        "price": 51000.0,  # ~2% deviation
        "quantity": 0.1
    }
    
    result = guard.validate(order, snapshot)
    
    assert result.passed is True
    assert result.reason_code == "OK"
    assert result.details["deviation_pct"] < 5.0


def test_price_guard_blocks_market_order_no_liquidity():
    """Price guard blocks market order when orderbook side is empty"""
    guard = PriceSanityGuard(band_pct=5.0)
    
    # BUY order needs asks (selling side), but asks are empty
    snapshot = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        bid=50000.0,
        bids=[PriceLevel(price=50000.0, amount=1.0)],
        asks=[],  # Empty - no liquidity
        last_update_ms=int(time.time() * 1000),
        version=1
    )
    
    order = {
        "symbol": "BTC/USDT",
        "side": "BUY",
        "order_style": "MARKET",
        "quantity": 0.1
    }
    
    result = guard.validate(order, snapshot)
    
    assert result.passed is False
    assert result.reason_code == "EXECUTION_BLOCKED_NO_LIQUIDITY"
    assert result.details["book_side"] == "asks"


def test_price_guard_allows_market_order_with_liquidity():
    """Price guard allows market order when liquidity present"""
    guard = PriceSanityGuard(band_pct=5.0)
    
    snapshot = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        bid=50000.0,
        ask=50001.0,
        bids=[PriceLevel(price=50000.0, amount=1.0)],
        asks=[PriceLevel(price=50001.0, amount=1.0)],
        last_update_ms=int(time.time() * 1000),
        version=1
    )
    
    order = {
        "symbol": "BTC/USDT",
        "side": "BUY",
        "order_style": "MARKET",
        "quantity": 0.1
    }
    
    result = guard.validate(order, snapshot)
    
    assert result.passed is True
    assert result.reason_code == "OK"
    assert "top_price" in result.details
    assert "top_amount" in result.details


def test_price_guard_fail_closed_on_bad_config():
    """Price guard fails closed when band_pct config is invalid"""
    # Invalid band_pct (> 50)
    guard = PriceSanityGuard(band_pct=100.0)
    
    # Should fail-closed (band_pct set to 0.0)
    assert guard.band_pct == 0.0
    
    # Any order should be blocked
    snapshot = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=50000.0,
        last_update_ms=int(time.time() * 1000)
    )
    
    order = {
        "symbol": "BTC/USDT",
        "side": "BUY",
        "order_style": "LIMIT",
        "price": 50001.0,
        "quantity": 0.1
    }
    
    result = guard.validate(order, snapshot)
    assert result.passed is False  # Blocked due to fail-closed config


def test_price_guard_blocks_malformed_order():
    """Price guard blocks malformed orders (missing fields)"""
    guard = PriceSanityGuard(band_pct=5.0)
    
    snapshot = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        last_update_ms=int(time.time() * 1000)
    )
    
    # Missing side field
    order = {
        "symbol": "BTC/USDT",
        "order_style": "LIMIT",
        "price": 50000.0
    }
    
    result = guard.validate(order, snapshot)
    
    assert result.passed is False
    assert result.reason_code == "EXECUTION_BLOCKED_GUARD_MALFORMED_ORDER"
    assert "missing_fields" in result.details


def test_price_guard_blocks_no_snapshot():
    """Price guard blocks when snapshot is None"""
    guard = PriceSanityGuard(band_pct=5.0)
    
    order = {
        "symbol": "BTC/USDT",
        "side": "BUY",
        "order_style": "LIMIT",
        "price": 50000.0,
        "quantity": 0.1
    }
    
    result = guard.validate(order, None)
    
    assert result.passed is False
    assert result.reason_code == "EXECUTION_BLOCKED_MD_NOT_VALID"
    assert result.details["snapshot_state"] == "MISSING"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
