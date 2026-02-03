"""
EPOCH E Phase E1: Strategy Registry
Strategy lifecycle management (register, enable, disable, shutdown)
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from .interfaces import IStrategy


logger = logging.getLogger(__name__)


class StrategyRegistry:
    """
    Strategy lifecycle registry
    
    Responsibilities:
    - Register / unregister strategies
    - Enable / disable at runtime
    - Track strategy versions
    - Reset state on enable
    - Graceful shutdown (on_stop)
    
    Features:
    - Per-strategy enable/disable (granular control)
    - Version tracking for auditing
    - Safe shutdown (calls on_stop on all strategies)
    """
    
    def __init__(self):
        """Initialize registry"""
        self._strategies: Dict[str, IStrategy] = {}  # strategy_id -> strategy
        self._enabled: Dict[str, bool] = {}  # strategy_id -> enabled
        
        logger.info("StrategyRegistry initialized")
    
    def register(self, strategy: IStrategy, enabled: bool = True):
        """
        Register a strategy
        
        Args:
            strategy: Strategy instance
            enabled: Whether to enable immediately (default True)
        
        Raises:
            ValueError: If strategy_id already registered
        """
        if strategy.strategy_id in self._strategies:
            raise ValueError(f"Strategy already registered: {strategy.strategy_id}")
        
        self._strategies[strategy.strategy_id] = strategy
        self._enabled[strategy.strategy_id] = enabled
        
        logger.info(
            f"Strategy registered: {strategy.strategy_id} (version={strategy.version}, enabled={enabled})"
        )
    
    def unregister(self, strategy_id: str):
        """
        Unregister a strategy (calls on_stop first)
        
        Args:
            strategy_id: Strategy ID
        
        Raises:
            KeyError: If strategy not found
        """
        if strategy_id not in self._strategies:
            raise KeyError(f"Strategy not found: {strategy_id}")
        
        # Call on_stop before unregistering
        strategy = self._strategies[strategy_id]
        try:
            strategy.on_stop()
        except Exception as e:
            logger.error(f"Error in on_stop for {strategy_id}: {e}", exc_info=True)
        
        del self._strategies[strategy_id]
        del self._enabled[strategy_id]
        
        logger.info(f"Strategy unregistered: {strategy_id}")
    
    def enable(self, strategy_id: str):
        """
        Enable a strategy
        
        Args:
            strategy_id: Strategy ID
        
        Raises:
            KeyError: If strategy not found
        """
        if strategy_id not in self._strategies:
            raise KeyError(f"Strategy not found: {strategy_id}")
        
        self._enabled[strategy_id] = True
        logger.info(f"Strategy enabled: {strategy_id}")
    
    def disable(self, strategy_id: str):
        """
        Disable a strategy
        
        Args:
            strategy_id: Strategy ID
        
        Raises:
            KeyError: If strategy not found
        """
        if strategy_id not in self._strategies:
            raise KeyError(f"Strategy not found: {strategy_id}")
        
        self._enabled[strategy_id] = False
        logger.info(f"Strategy disabled: {strategy_id}")
    
    def is_enabled(self, strategy_id: str) -> bool:
        """
        Check if strategy is enabled
        
        Args:
            strategy_id: Strategy ID
        
        Returns:
            True if enabled, False otherwise
        """
        return self._enabled.get(strategy_id, False)
    
    def get_strategy(self, strategy_id: str) -> Optional[IStrategy]:
        """
        Get strategy by ID
        
        Args:
            strategy_id: Strategy ID
        
        Returns:
            Strategy instance or None
        """
        return self._strategies.get(strategy_id)
    
    def get_all_strategies(self) -> List[IStrategy]:
        """
        Get all registered strategies
        
        Returns:
            List of all strategies
        """
        return list(self._strategies.values())
    
    def get_enabled_strategies(self) -> List[IStrategy]:
        """
        Get all enabled strategies
        
        Returns:
            List of enabled strategies
        """
        return [
            strategy
            for strategy_id, strategy in self._strategies.items()
            if self._enabled.get(strategy_id, False)
        ]
    
    def shutdown(self):
        """
        Graceful shutdown (call on_stop on all strategies)
        """
        logger.info("Shutting down StrategyRegistry...")
        
        for strategy_id, strategy in list(self._strategies.items()):
            try:
                strategy.on_stop()
                logger.info(f"Strategy stopped: {strategy_id}")
            except Exception as e:
                logger.error(f"Error in on_stop for {strategy_id}: {e}", exc_info=True)
        
        logger.info("StrategyRegistry shutdown complete")
