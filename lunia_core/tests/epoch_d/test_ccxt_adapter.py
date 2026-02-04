"""
EPOCH D Phase D1: CCXT Adapter Tests
Tests normalization, error mapping, security
"""
import pytest
import os
from unittest.mock import Mock, patch
import ccxt

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lunia_core.app.services.market_data.adapters.ccxt_adapter import CCXTAdapter
from lunia_core.app.services.market_data.adapters.mock_adapter import MockExchangeAdapter
from lunia_core.app.services.market_data.models import TickerSnapshot, Candle, OrderBookSnapshot, BalanceSnapshot
from lunia_core.app.services.execution.exceptions import HardError, SoftError


def test_mock_adapter_normalization():
    """Mock adapter returns properly normalized models"""
    adapter = MockExchangeAdapter("test_exchange")
    
    # Test ticker
    ticker = adapter.fetch_ticker("BTC/USDT")
    assert isinstance(ticker, TickerSnapshot)
    assert ticker.exchange == "test_exchange"
    assert ticker.symbol == "BTC/USDT"
    assert ticker.bid is not None
    assert ticker.ask is not None
    assert ticker.received_at_ms > 0
    
    # Test OHLCV
    candles = adapter.fetch_ohlcv("BTC/USDT", "1m", limit=5)
    assert len(candles) > 0
    assert all(isinstance(c, Candle) for c in candles)
    assert candles[0].exchange == "test_exchange"
    assert candles[0].volume >= 0
    
    # Test orderbook
    orderbook = adapter.fetch_order_book("BTC/USDT", depth=10)
    assert isinstance(orderbook, OrderBookSnapshot)
    assert len(orderbook.bids) == 10
    assert len(orderbook.asks) == 10
    assert all(b.price > 0 for b in orderbook.bids)
    assert all(a.price > 0 for a in orderbook.asks)
    
    # Test balance
    balance = adapter.fetch_balance()
    assert isinstance(balance, BalanceSnapshot)
    assert "BTC" in balance.total
    assert "USDT" in balance.free


def test_error_mapping_network_to_soft():
    """NetworkError should map to SoftError"""
    adapter = MockExchangeAdapter()
    adapter.configure_error("fetch_ticker", ccxt.NetworkError("Connection failed"))
    
    with pytest.raises(SoftError):
        adapter.fetch_ticker("BTC/USDT")


def test_error_mapping_auth_to_hard():
    """AuthenticationError should map to HardError"""
    # Use CCXT adapter with mock exchange
    with patch.dict(os.environ, {"LUNIA_EXCHANGE_ID": "binance"}):
        with patch('ccxt.binance') as mock_exchange_class:
            mock_exchange = Mock()
            mock_exchange.load_markets = Mock()
            mock_exchange.fetch_ticker = Mock(side_effect=ccxt.AuthenticationError("Invalid API key"))
            mock_exchange_class.return_value = mock_exchange
            
            adapter = CCXTAdapter()
            
            with pytest.raises(HardError) as exc_info:
                adapter.fetch_ticker("BTC/USDT")
            
            assert "Authentication failed" in str(exc_info.value)


def test_error_mapping_insufficient_funds_to_hard():
    """InsufficientFunds should map to HardError"""
    adapter = CCXTAdapter.__new__(CCXTAdapter)  # Skip init
    adapter.exchange_id = "test"
    adapter._api_key = None
    adapter._secret = None
    
    error = ccxt.InsufficientFunds("Not enough balance")
    mapped = adapter._map_ccxt_exception(error)
    
    assert isinstance(mapped, HardError)
    assert "Insufficient funds" in str(mapped)


def test_error_mapping_unknown_to_soft():
    """Unknown errors should default to SoftError (fail-closed ambiguous)"""
    adapter = CCXTAdapter.__new__(CCXTAdapter)
    adapter.exchange_id = "test"
    adapter._api_key = None
    adapter._secret = None
    
    error = Exception("Unknown exchange error")
    mapped = adapter._map_ccxt_exception(error)
    
    assert isinstance(mapped, SoftError)
    assert "Unknown exchange error" in str(mapped)


def test_error_mapping_timeout_to_soft():
    """RequestTimeout should map to SoftError"""
    adapter = CCXTAdapter.__new__(CCXTAdapter)
    adapter.exchange_id = "test"
    adapter._api_key = None
    adapter._secret = None
    
    error = ccxt.RequestTimeout("Request timed out")
    mapped = adapter._map_ccxt_exception(error)
    
    assert isinstance(mapped, SoftError)


def test_error_mapping_502_to_soft():
    """502/503/504 errors should map to SoftError"""
    adapter = CCXTAdapter.__new__(CCXTAdapter)
    adapter.exchange_id = "test"
    adapter._api_key = None
    adapter._secret = None
    
    error = ccxt.ExchangeError("502 Bad Gateway")
    mapped = adapter._map_ccxt_exception(error)
    
    assert isinstance(mapped, SoftError)
    assert "Upstream error" in str(mapped)


def test_no_secrets_in_error_messages():
    """API key/secret should NEVER appear in error messages"""
    adapter = CCXTAdapter.__new__(CCXTAdapter)
    adapter.exchange_id = "test"
    adapter._api_key = "test_api_key_12345"
    adapter._secret = "test_secret_67890"
    
    error = Exception(f"Error with key {adapter._api_key} and secret {adapter._secret}")
    safe_msg = adapter._safe_error_message(error)
    
    # Verify secrets are sanitized
    assert adapter._api_key not in safe_msg
    assert adapter._secret not in safe_msg
    assert "***API_KEY***" in safe_msg
    assert "***SECRET***" in safe_msg


def test_retry_backoff_logic():
    """Retry should use exponential backoff with jitter"""
    adapter = CCXTAdapter.__new__(CCXTAdapter)
    adapter.exchange_id = "test"
    adapter._api_key = None
    adapter._secret = None
    adapter.MAX_RETRY_ATTEMPTS = 3
    adapter.BASE_BACKOFF_SEC = 0.5
    adapter.MAX_BACKOFF_SEC = 5.0
    
    # Mock function that fails twice then succeeds
    call_count = [0]
    
    def mock_func():
        call_count[0] += 1
        if call_count[0] < 3:
            raise ccxt.NetworkError("Temporary failure")
        return "SUCCESS"
    
    # Should retry and eventually succeed
    result = adapter._retry_with_backoff(mock_func)
    assert result == "SUCCESS"
    assert call_count[0] == 3  # Failed twice, succeeded on third


def test_retry_no_retry_on_hard_error():
    """Hard errors should NOT be retried"""
    adapter = CCXTAdapter.__new__(CCXTAdapter)
    adapter.exchange_id = "test"
    adapter._api_key = None
    adapter._secret = None
    
    call_count = [0]
    
    def mock_func():
        call_count[0] += 1
        raise ccxt.InsufficientFunds("Not enough balance")
    
    # Should fail immediately without retry
    with pytest.raises(HardError):
        adapter._retry_with_backoff(mock_func)
    
    assert call_count[0] == 1  # Only one attempt (no retry)


def test_retry_exhausts_max_attempts():
    """After max retries, SoftError should be raised"""
    adapter = CCXTAdapter.__new__(CCXTAdapter)
    adapter.exchange_id = "test"
    adapter._api_key = None
    adapter._secret = None
    adapter.MAX_RETRY_ATTEMPTS = 3
    
    call_count = [0]
    
    def mock_func():
        call_count[0] += 1
        raise ccxt.NetworkError("Persistent failure")
    
    # Should exhaust retries and raise SoftError
    with pytest.raises(SoftError):
        adapter._retry_with_backoff(mock_func)
    
    assert call_count[0] == 3  # All 3 attempts used


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
