"""
Phase 8.2A: Rate Limiter for Intent Persistence
Prevents self-DDoS by limiting persistence rate per (strategy_id, symbol)
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Sliding window rate limiter for intent persistence
    
    HARD LAWS:
    - O(1) amortized per check (no DB queries)
    - 60-second sliding window
    - Max 100 events per (strategy_id, symbol) per window
    - Thread-safe (intended for single-threaded StrategyEngine)
    
    Implementation:
    - Ring buffer per (strategy_id, symbol)
    - Stores timestamps of last N events
    - Evicts expired timestamps on each check
    """
    
    def __init__(
        self,
        window_seconds: int = 60,
        max_events: int = 100
    ):
        """
        Initialize rate limiter
        
        Args:
            window_seconds: Sliding window duration (default 60s)
            max_events: Max events per window per key (default 100)
        """
        self.window_seconds = window_seconds
        self.max_events = max_events
        
        # Rate limit state: (strategy_id, symbol) -> deque of timestamps
        self._event_windows: Dict[Tuple[str, str], deque] = defaultdict(lambda: deque(maxlen=max_events))
        
        logger.info(f"RateLimiter initialized: {max_events} events per {window_seconds}s window")
    
    def should_persist(self, strategy_id: str, symbol: str) -> Tuple[bool, str]:
        """
        Check if intent should be persisted given rate limits
        
        Args:
            strategy_id: Strategy identifier
            symbol: Trading symbol
        
        Returns:
            (should_persist, reason) tuple
            - should_persist: True if within rate limit, False if exceeded
            - reason: Explanation if rate limited
        """
        now = time.time()
        key = (strategy_id, symbol)
        window = self._event_windows[key]
        
        # Evict expired timestamps (O(k) where k = expired count)
        cutoff = now - self.window_seconds
        while window and window[0] < cutoff:
            window.popleft()
        
        # Check if rate limit exceeded
        if len(window) >= self.max_events:
            logger.warning(
                f"Rate limit exceeded: {strategy_id}:{symbol} "
                f"({len(window)} events in {self.window_seconds}s window)"
            )
            return False, f"rate_limit_exceeded_{self.window_seconds}s"
        
        # Within limit: record timestamp
        window.append(now)
        return True, ""
    
    def get_current_rate(self, strategy_id: str, symbol: str) -> int:
        """
        Get current event count in window for debugging
        
        Args:
            strategy_id: Strategy identifier
            symbol: Trading symbol
        
        Returns:
            Number of events in current window
        """
        key = (strategy_id, symbol)
        window = self._event_windows.get(key)
        
        if not window:
            return 0
        
        # Clean expired
        now = time.time()
        cutoff = now - self.window_seconds
        while window and window[0] < cutoff:
            window.popleft()
        
        return len(window)
    
    def reset(self, strategy_id: str = None, symbol: str = None):
        """
        Reset rate limit state (for testing or manual intervention)
        
        Args:
            strategy_id: Strategy to reset (None = all)
            symbol: Symbol to reset (None = all for given strategy)
        """
        if strategy_id is None:
            self._event_windows.clear()
            logger.info("Rate limiter reset (all)")
        elif symbol is None:
            # Reset all symbols for given strategy
            keys_to_remove = [k for k in self._event_windows.keys() if k[0] == strategy_id]
            for key in keys_to_remove:
                del self._event_windows[key]
            logger.info(f"Rate limiter reset: {strategy_id} (all symbols)")
        else:
            # Reset specific strategy-symbol pair
            key = (strategy_id, symbol)
            if key in self._event_windows:
                del self._event_windows[key]
            logger.info(f"Rate limiter reset: {strategy_id}:{symbol}")
