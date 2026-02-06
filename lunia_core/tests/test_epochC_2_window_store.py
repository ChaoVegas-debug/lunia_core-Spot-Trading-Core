"""
Test Epoch C.2 — Window Store and Circuit Breaker

Tests for time-window counters and consecutive block tracking.
"""
import pytest

from lunia_core.app.services.risk_governor.window_store import (
    CircuitBreakerState,
    WindowCounterStore,
)


# =============================================================================
# WINDOW COUNTER TESTS
# =============================================================================

def test_increment_and_count():
    """Basic increment and count functionality"""
    store = WindowCounterStore()
    
    # Increment across time
    store.increment("binance:BTCUSDT", 1000)
    store.increment("binance:BTCUSDT", 2000)
    store.increment("binance:BTCUSDT", 3000)
    
    # Count window [0, 3000]
    count = store.count_last_ms("binance:BTCUSDT", now_ms=3000, window_ms=3000)
    assert count == 3


def test_window_rolloff():
    """Events outside window are not counted"""
    store = WindowCounterStore()
    
    # Events at 1000, 2000, 10000
    store.increment("binance:BTCUSDT", 1000)
    store.increment("binance:BTCUSDT", 2000)
    store.increment("binance:BTCUSDT", 10000)
    
    # Window [9000, 12000] → only event at 10000
    count = store.count_last_ms("binance:BTCUSDT", now_ms=12000, window_ms=3000)
    assert count == 1


def test_per_key_isolation():
    """Keys are isolated from each other"""
    store = WindowCounterStore()
    
    store.increment("binance:BTCUSDT", 1000)
    store.increment("binance:BTCUSDT", 2000)
    store.increment("binance:ETHUSDT", 1500)
    
    count_btc = store.count_last_ms("binance:BTCUSDT", now_ms=3000, window_ms=3000)
    count_eth = store.count_last_ms("binance:ETHUSDT", now_ms=3000, window_ms=3000)
    
    assert count_btc == 2
    assert count_eth == 1


def test_deterministic_clock():
    """Deterministic behavior with injected timestamps"""
    store = WindowCounterStore()
    
    # Inject specific timestamps
    store.increment("test:KEY", 1000000)
    store.increment("test:KEY", 1001000)
    store.increment("test:KEY", 1002000)
    
    # Window [999000, 1003000] → all 3 events
    count = store.count_last_ms("test:KEY", now_ms=1003000, window_ms=4000)
    assert count == 3
    
    # Window [1001500, 1003000] → only last event
    count = store.count_last_ms("test:KEY", now_ms=1003000, window_ms=1500)
    assert count == 1


def test_purge_bounded_memory():
    """Purge removes old events to bound memory"""
    store = WindowCounterStore()
    
    # Add events at various times
    store.increment("key1", 1000)
    store.increment("key1", 5000)
    store.increment("key2", 10000)
    store.increment("key2", 20000)
    
    # Purge events older than 15000ms before now (30000)
    # Retention window: [15000, 30000]
    store.purge(now_ms=30000, retention_ms=15000)
    
    # key1 events (1000, 5000) should be purged
    # key2 event (10000) should be purged
    # key2 event (20000) should remain
    
    count_key1 = store.count_last_ms("key1", now_ms=30000, window_ms=30000)
    count_key2 = store.count_last_ms("key2", now_ms=30000, window_ms=30000)
    
    assert count_key1 == 0
    assert count_key2 == 1


# =============================================================================
# CIRCUIT BREAKER TESTS
# =============================================================================

def test_circuit_breaker_increment():
    """Circuit breaker increments consecutive blocks"""
    cb = CircuitBreakerState()
    
    count1 = cb.record_block("binance", "BTCUSDT")
    assert count1 == 1
    
    count2 = cb.record_block("binance", "BTCUSDT")
    assert count2 == 2
    
    count3 = cb.record_block("binance", "BTCUSDT")
    assert count3 == 3


def test_circuit_breaker_reset():
    """Circuit breaker resets on ALLOW"""
    cb = CircuitBreakerState()
    
    cb.record_block("binance", "BTCUSDT")
    cb.record_block("binance", "BTCUSDT")
    
    assert cb.get_count("binance", "BTCUSDT") == 2
    
    # Reset
    cb.reset("binance", "BTCUSDT")
    
    assert cb.get_count("binance", "BTCUSDT") == 0


def test_circuit_breaker_per_adapter_symbol():
    """Circuit breaker isolates by (adapter, symbol)"""
    cb = CircuitBreakerState()
    
    cb.record_block("binance", "BTCUSDT")
    cb.record_block("binance", "BTCUSDT")
    cb.record_block("binance", "ETHUSDT")
    cb.record_block("kraken", "BTCUSDT")
    
    assert cb.get_count("binance", "BTCUSDT") == 2
    assert cb.get_count("binance", "ETHUSDT") == 1
    assert cb.get_count("kraken", "BTCUSDT") == 1
