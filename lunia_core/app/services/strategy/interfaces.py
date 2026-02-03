"""
EPOCH E Phase E1: Strategy Interface
Abstract base class for all trading strategies
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .models import StrategyContext, IntentProposal


class IStrategy(ABC):
    """
    Strategy interface (Abstract Base Class)
    
    ALL strategies must inherit from this interface.
    
    LOCKED INVARIANTS:
    - Strategies have ZERO execution authority
    - on_tick() MUST be pure (no side effects)
    - on_tick() MUST be deterministic (same input → same output)
    - Strategies CANNOT access adapters, workers, queues
    - Output = IntentProposal (passive, explainable, rejectable)
    
    Lifecycle:
    1. Engine calls on_init(context) once at strategy startup
    2. Engine calls on_tick(context) on every NEW snapshot version
    3. Engine calls on_stop() at strategy shutdown or disable
    """
    
    @property
    @abstractmethod
    def strategy_id(self) -> str:
        """
        Unique strategy identifier
        
        Returns:
            Strategy ID (e.g., "momentum_v1", "mean_reversion_btc")
        """
        pass
    
    @property
    @abstractmethod
    def version(self) -> str:
        """
        Strategy version (semantic versioning recommended)
        
        Returns:
            Version string (e.g., "1.0.0", "2.1.3-alpha")
        """
        pass
    
    @abstractmethod
    def on_init(self, context: StrategyContext):
        """
        Initialize strategy (called once at startup)
        
        Use this for:
        - Loading configuration
        - Initializing internal state
        - Warm-up logic
        
        Args:
            context: Strategy context (initial snapshot)
        """
        pass
    
    @abstractmethod
    def on_tick(self, context: StrategyContext) -> Optional[IntentProposal]:
        """
        Evaluate strategy on new market data (event-driven)
        
        CRITICAL RULES:
        - MUST be pure (no side effects)
        - MUST be deterministic (same input → same output)
        - MUST NOT access external state
        - MUST NOT call adapters or workers
        - Output = IntentProposal (passive proposal)
        
        Args:
            context: Strategy context (current snapshot, symbol, version)
        
        Returns:
            IntentProposal if signal generated, None otherwise
        """
        pass
    
    @abstractmethod
    def on_stop(self):
        """
        Cleanup on strategy shutdown or disable
        
        Use this for:
        - Closing resources
        - Persisting state
        - Final logging
        """
        pass
