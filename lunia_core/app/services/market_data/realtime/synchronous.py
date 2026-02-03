"""
EPOCH D Phase D3.2.1: Thread-Safe Snapshot Cache
Synchronous bridge for sharing async market data with sync execution worker
"""
from __future__ import annotations

import threading
from typing import Dict, Optional
from copy import deepcopy

from .models import MarketSnapshot


class ThreadSafeSnapshotCache:
    """
    Thread-safe snapshot cache for async-to-sync data sharing
    
    Features:
    - O(1) reads (no event loop interaction)
    - Atomic visibility (RLock protection)
    - Copy-on-write semantics (immutable references)
    - Fail-closed (missing key → None)
    
    Usage:
    - Writer (Async Engine): Calls update(symbol, snapshot) after internal async lock
    - Reader (Sync Worker): Calls get(symbol) for instant O(1) read
    """
    
    def __init__(self):
        """Initialize thread-safe cache"""
        self._cache: Dict[str, MarketSnapshot] = {}
        self._lock = threading.RLock()
    
    def update(self, symbol: str, snapshot: MarketSnapshot):
        """
        Update snapshot for symbol (atomic)
        
        Args:
            symbol: Trading pair
            snapshot: Market snapshot (will be deep copied for safety)
        """
        with self._lock:
            # Deep copy to ensure immutability (async engine cannot modify reader's data)
            self._cache[symbol] = deepcopy(snapshot)
    
    def get(self, symbol: str) -> Optional[MarketSnapshot]:
        """
        Get snapshot for symbol (O(1), non-blocking)
        
        Args:
            symbol: Trading pair
        
        Returns:
            MarketSnapshot (deep copy) or None if not found
        """
        with self._lock:
            snapshot = self._cache.get(symbol)
            if snapshot is None:
                return None
            # Return deep copy to prevent external mutation
            return deepcopy(snapshot)
    
    def get_all_symbols(self) -> list[str]:
        """
        Get all tracked symbols
        
        Returns:
            List of symbols
        """
        with self._lock:
            return list(self._cache.keys())
    
    def clear(self):
        """Clear all snapshots"""
        with self._lock:
            self._cache.clear()
