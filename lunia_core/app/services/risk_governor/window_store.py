"""
Window Store and Circuit Breaker — Time-Based Safety Guards

Deterministic time-window counters with injected clock for reproducibility.
Circuit breaker tracks consecutive blocks to prevent system thrashing.
"""
from collections import defaultdict, deque
from threading import Lock
from typing import DefaultDict, Deque, Tuple


class WindowCounterStore:
    """
    Deterministic time-window counter.
    
    Tracks events in time windows (e.g., orders per hour).
    Thread-safe, bounded memory via purge.
    """
    
    def __init__(self):
        # key -> [(timestamp_ms, count), ...]
        self._store: DefaultDict[str, Deque[Tuple[int, int]]] = defaultdict(deque)
        self._lock = Lock()
    
    def increment(self, key: str, ts_ms: int) -> int:
        """
        Increment counter for key at timestamp.
        
        Args:
            key: Counter key (e.g., "binance:BTCUSDT")
            ts_ms: Event timestamp in milliseconds
            
        Returns:
            New count value
        """
        with self._lock:
            # Append event
            self._store[key].append((ts_ms, 1))
            return len(self._store[key])
    
    def count_last_ms(self, key: str, now_ms: int, window_ms: int) -> int:
        """
        Count events in time window [now - window, now].
        
        Args:
            key: Counter key
            now_ms: Current timestamp
            window_ms: Window size in milliseconds
            
        Returns:
            Count of events in window
        """
        with self._lock:
            if key not in self._store:
                return 0
            
            cutoff_ms = now_ms - window_ms
            
            # Count events >= cutoff
            count = sum(
                1 for (ts, _) in self._store[key]
                if ts >= cutoff_ms
            )
            
            return count
    
    def purge(self, now_ms: int, retention_ms: int = 86400000) -> None:
        """
        Remove events older than retention window.
        
        Prevents unbounded memory growth in production.
        
        Args:
            now_ms: Current timestamp
            retention_ms: How far back to keep (default: 24 hours)
        """
        with self._lock:
            cutoff_ms = now_ms - retention_ms
            
            for key in list(self._store.keys()):
                # Filter out old events
                self._store[key] = deque(
                    (ts, count) for (ts, count) in self._store[key]
                    if ts >= cutoff_ms
                )
                
                # Remove empty keys
                if not self._store[key]:
                    del self._store[key]
    
    def clear(self) -> None:
        """Clear all counters (testing only)"""
        with self._lock:
            self._store.clear()


class CircuitBreakerState:
    """
    Track consecutive blocks to detect system thrashing.
    
    Recommends halt after N consecutive blocks on same (adapter, symbol).
    """
    
    def __init__(self):
        # (adapter, symbol) -> consecutive_block_count
        self._blocks: DefaultDict[Tuple[str, str], int] = defaultdict(int)
        self._lock = Lock()
    
    def record_block(self, adapter_name: str, symbol: str) -> int:
        """
        Record a block event, return new consecutive count.
        
        Args:
            adapter_name: Exchange adapter name
            symbol: Trading symbol
            
        Returns:
            New consecutive block count
        """
        with self._lock:
            key = (adapter_name, symbol)
            self._blocks[key] += 1
            return self._blocks[key]
    
    def reset(self, adapter_name: str, symbol: str) -> None:
        """
        Reset consecutive blocks (on ALLOW).
        
        Args:
            adapter_name: Exchange adapter name
            symbol: Trading symbol
        """
        with self._lock:
            key = (adapter_name, symbol)
            self._blocks[key] = 0
    
    def get_count(self, adapter_name: str, symbol: str) -> int:
        """
        Get current consecutive block count.
        
        Args:
            adapter_name: Exchange adapter name
            symbol: Trading symbol
            
        Returns:
            Current consecutive block count
        """
        with self._lock:
            key = (adapter_name, symbol)
            return self._blocks[key]
    
    def clear(self) -> None:
        """Clear all state (testing only)"""
        with self._lock:
            self._blocks.clear()
