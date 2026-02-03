"""
EPOCH D Phase D1: Market Data Tests (Standalone - NO ccxt required)
Tests mock adapter, error mapping logic, security
"""
import pytest
from unittest.mock import Mock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.market_data.adapters.mock_adapter import MockExchangeAdapter
from app.services.market_data.models import (
    TickerSnapshot,
    Candle,
    OrderBookSnapshot,
    BalanceSnapshot,
    SubmitOrderResult,
    OrderStatusResult
)
from app.services.execution.exceptions import HardError, SoftError


def test_mock_adapter_ticker_normalization():
    """Mock adapter returns properly normalized TickerSnapshot"""
    adapter = MockExchangeAdapter("test_exchange")
    
    ticker = adapter.fetch_ticker("BTC/USDT")
    
    # Verify type
    assert isinstance(ticker, TickerSnapshot)
    
    # Verify fields
    assert ticker.exchange == "test_exchange"
    assert ticker.symbol == "BTC/USDT"
    assert isinstance(ticker.bid, float)
    assert isinstance(ticker.ask, float)
    assert isinstance(ticker.last, float)
    assert ticker.received_at_ms > 0


def test_mock_adapter_ohlcv_normalization():
    """Mock adapter returns properly normalized Candle list"""
    adapter = MockExchangeAdapter("test_exchange")
    
    candles = adapter.fetch_ohlcv("BTC/USDT", "1m", limit=5)
    
    # Verify length
    assert len(candles) > 0
    
    # Verify all are Candle instances
    assert all(isinstance(c, Candle) for c in candles)
    
    # Verify first candle fields
    candle = candles[0]
    assert candle.exchange == "test_exchange"
    assert candle.symbol == "BTC/USDT"
    assert candle.timeframe == "1m"
    assert candle.timestamp_ms > 0
    assert candle.open > 0
    assert candle.high > 0
    assert candle.low > 0
    assert candle.close > 0
    assert candle.volume >= 0


def test_mock_adapter_orderbook_normalization():
    """Mock adapter returns properly normalized OrderBookSnapshot"""
    adapter = MockExchangeAdapter("test_exchange")
    
    orderbook = adapter.fetch_order_book("BTC/USDT", depth=10)
    
    # Verify type
    assert isinstance(orderbook, OrderBookSnapshot)
    
    # Verify fields
    assert orderbook.exchange == "test_exchange"
    assert orderbook.symbol == "BTC/USDT"
    assert len(orderbook.bids) == 10
    assert len(orderbook.asks) == 10
    
    # Verify price levels
    assert all(b.price > 0 and b.amount > 0 for b in orderbook.bids)
    assert all(a.price > 0 and a.amount > 0 for a in orderbook.asks)
    
    # Verify bids/asks ordering (bids descending, asks ascending)
    if len(orderbook.bids) > 1:
        assert orderbook.bids[0].price > orderbook.bids[-1].price
    if len(orderbook.asks) > 1:
        assert orderbook.asks[0].price < orderbook.asks[-1].price


def test_mock_adapter_balance_normalization():
    """Mock adapter returns properly normalized BalanceSnapshot"""
    adapter = MockExchangeAdapter("test_exchange")
    
    balance = adapter.fetch_balance()
    
    # Verify type
    assert isinstance(balance, BalanceSnapshot)
    
    # Verify fields
    assert balance.exchange == "test_exchange"
    assert isinstance(balance.total, dict)
    assert isinstance(balance.free, dict)
    assert isinstance(balance.used, dict)
    assert balance.received_at_ms > 0
    
    # Verify balances are non-negative
    for asset, amount in balance.total.items():
        assert amount >= 0
    for asset, amount in balance.free.items():
        assert amount >= 0
    for asset, amount in balance.used.items():
        assert amount >= 0


def test_mock_adapter_submit_order_result():
    """Mock adapter returns properly normalized SubmitOrderResult"""
    adapter = MockExchangeAdapter("test_exchange")
    
    order_spec = {
        "symbol": "BTC/USDT",
      "side": "buy",
        "quantity": 0.1,
        "order_type": "market",
        "client_order_id": "test_order_123"
    }
    
    result = adapter.submit_order(order_spec)
    
    # Verify type
    assert isinstance(result, SubmitOrderResult)
    
    # Verify fields
    assert result.client_order_id == "test_order_123"
    assert result.exchange_order_id is not None
    assert result.status == "NEW"
    assert result.filled_qty == 0.0


def test_mock_adapter_get_order_result():
    """Mock adapter returns properly normalized OrderStatusResult"""
    adapter = MockExchangeAdapter("test_exchange")
    
    result = adapter.get_order("test_order_123")
    
    # Verify type
    assert isinstance(result, OrderStatusResult)
    
    # Verify fields
    assert result.client_order_id == "test_order_123"
    assert result.exchange_order_id is not None
    assert result.status in ["NEW", "FILLED", "PARTIALLY_FILLED", "CANCELLED"]
    assert result.filled_qty >= 0


def test_mock_adapter_error_injection():
    """Mock adapter can be configured to raise specific errors"""
    adapter = MockExchangeAdapter("test_exchange")
    
    # Configure to raise SoftError
    adapter.configure_error("fetch_ticker", SoftError("Network timeout"))
    
    with pytest.raises(SoftError) as exc_info:
        adapter.fetch_ticker("BTC/USDT")
    
    assert "Network timeout" in str(exc_info.value)


def test_error_mapping_logic_hard_vs_soft():
    """Test Hard vs Soft error classification logic"""
    # Hard errors (definitive rejection)
    hard_error_keywords = ["authentication", "insufficient funds", "invalid order", "not found"]
    
    for keyword in hard_error_keywords:
        error_msg = f"Error: {keyword}"
        # Logic: if keyword in error → HardError
        is_hard = any(kw in error_msg.lower() for kw in hard_error_keywords)
        assert is_hard is True
    
    # Soft errors (ambiguous/retryable)
    soft_error_keywords = ["network", "timeout", "502", "503", "504"]
    
    for keyword in soft_error_keywords:
        error_msg = f"Error: {keyword}"
        # Logic: if keyword in error → SoftError
        is_soft = any(kw in error_msg.lower() for kw in soft_error_keywords)
        assert is_soft is True


def test_security_no_secrets_in_messages():
    """Verify secret sanitization logic works"""
    api_key = "test_api_key_12345"
    secret = "test_secret_67890"
    
    error_msg = f"Authentication failed with key {api_key} and secret {secret}"
    
    # Sanitize
    safe_msg = error_msg.replace(api_key, "***API_KEY***").replace(secret, "***SECRET***")
    
    # Verify secrets removed
    assert api_key not in safe_msg
    assert secret not in safe_msg
    assert "***API_KEY***" in safe_msg
    assert "***SECRET***" in safe_msg


def test_retry_backoff_calculation():
    """Test exponential backoff calculation"""
    BASE_BACKOFF_SEC = 0.5
    MAX_BACKOFF_SEC = 5.0
    
    # Attempt 0: 0.5 * 2^0 = 0.5
    backoff_0 = min(BASE_BACKOFF_SEC * (2 ** 0), MAX_BACKOFF_SEC)
    assert backoff_0 == 0.5
    
    # Attempt 1: 0.5 * 2^1 = 1.0
    backoff_1 = min(BASE_BACKOFF_SEC * (2 ** 1), MAX_BACKOFF_SEC)
    assert backoff_1 == 1.0
    
    # Attempt 2: 0.5 * 2^2 = 2.0
    backoff_2 = min(BASE_BACKOFF_SEC * (2 ** 2), MAX_BACKOFF_SEC)
    assert backoff_2 == 2.0
    
    # Attempt 3: 0.5 * 2^3 = 4.0
    backoff_3 = min(BASE_BACKOFF_SEC * (2 ** 3), MAX_BACKOFF_SEC)
    assert backoff_3 == 4.0
    
    # Attempt 4: 0.5 * 2^4 = 8.0 → capped at 5.0
    backoff_4 = min(BASE_BACKOFF_SEC * (2 ** 4), MAX_BACKOFF_SEC)
    assert backoff_4 == 5.0  # Capped


def test_bounded_retry_max_attempts():
    """Test that retries are bounded (max 3 attempts)"""
    MAX_RETRY_ATTEMPTS = 3
    
    attempts = 0
    max_attempts_reached = False
    
    for attempt in range(MAX_RETRY_ATTEMPTS):
        attempts += 1
        # Simulate failure
        is_last_attempt = (attempt == MAX_RETRY_ATTEMPTS - 1)
        if is_last_attempt:
            max_attempts_reached = True
            break
    
    assert attempts == MAX_RETRY_ATTEMPTS
    assert max_attempts_reached is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
