"""
EPOCH E Phase E2: Governance Context
Stateful governance state (cooldowns, rate limits, etc.)
"""
from __future__ import annotations

import time
from typing import Dict


class GovernanceContext:
    """
    Governance internal state for stateful rules
    
    Purpose:
    - Track execution times for cooldown enforcement
    - Future: rate limits, circuit breakers, exposure tracking
    
    LOCKED INVARIANTS:
    - State is deterministic
    - State is owned exclusively by GovernanceEngine
    - Strategies CANNOT access this state
    - State updates ONLY on APPROVE decisions
    
    Design:
    - last_execution_times: {strategy_id: {symbol: timestamp_ms}}
    """
    
    def __init__(self):
        """Initialize governance context"""
        # Last execution times: strategy_id -> symbol -> timestamp_ms
        self._last_execution_times: Dict[str, Dict[str, int]] = {}
    
    def get_last_execution_time(self, strategy_id: str, symbol: str) -> int:
        """
        Get last execution timestamp for strategy+symbol
        
        Args:
            strategy_id: Strategy identifier
            symbol: Trading pair
        
        Returns:
            Last execution timestamp in ms (0 if never executed)
        """
        return self._last_execution_times.get(strategy_id, {}).get(symbol, 0)
    
    def record_execution(self, strategy_id: str, symbol: str, timestamp_ms: int | None = None):
        """
        Record execution time for strategy+symbol
        
        Args:
            strategy_id: Strategy identifier
            symbol: Trading pair
            timestamp_ms: Timestamp (defaults to now)
        """
        if timestamp_ms is None:
            timestamp_ms = int(time.time() * 1000)
        
        if strategy_id not in self._last_execution_times:
            self._last_execution_times[strategy_id] = {}
        
        self._last_execution_times[strategy_id][symbol] = timestamp_ms
    
    def get_all_execution_times(self) -> Dict[str, Dict[str, int]]:
        """
        Get all execution times (for debugging/auditing)
        
        Returns:
            Deep copy of execution times
        """
        return {
            strategy_id: dict(symbols)
            for strategy_id, symbols in self._last_execution_times.items()
        }
    
    def reset(self):
        """Reset all state (for testing or manual intervention)"""
        self._last_execution_times.clear()
