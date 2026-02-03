"""
EPOCH E Phase E2: Governance Rule Registry
Lifecycle management for governance rules
"""
from __future__ import annotations

import logging
from typing import List

from .rules.base import GovernanceRule


logger = logging.getLogger(__name__)


class GovernanceRuleRegistry:
    """
    Governance rule registry with lifecycle management
    
    Responsibilities:
    - Register / unregister rules
    - Enable / disable at runtime
    - Explicit, deterministic rule ordering
    
    Features:
    - Per-rule enable/disable
    - Deterministic evaluation order (registration order)
    - Safe shutdown
    """
    
    def __init__(self):
        """Initialize rule registry"""
        self._rules: List[GovernanceRule] = []
        self._enabled: dict[str, bool] = {}
        
        logger.info("GovernanceRuleRegistry initialized")
    
    def register(self, rule: GovernanceRule, enabled: bool = True):
        """
        Register a governance rule
        
        Args:
            rule: GovernanceRule instance
            enabled: Whether to enable immediately (default True)
        
        Raises:
            ValueError: If rule_id already registered
        """
        if rule.rule_id in self._enabled:
            raise ValueError(f"Rule already registered: {rule.rule_id}")
        
        self._rules.append(rule)
        self._enabled[rule.rule_id] = enabled
        
        logger.info(f"Governance rule registered: {rule.rule_id} (enabled={enabled})")
    
    def unregister(self, rule_id: str):
        """
        Unregister a governance rule
        
        Args:
            rule_id: Rule identifier
        
        Raises:
            KeyError: If rule not found
        """
        # Find and remove rule
        rule_found = False
        for i, rule in enumerate(self._rules):
            if rule.rule_id == rule_id:
                self._rules.pop(i)
                rule_found = True
                break
        
        if not rule_found:
            raise KeyError(f"Rule not found: {rule_id}")
        
        del self._enabled[rule_id]
        
        logger.info(f"Governance rule unregistered: {rule_id}")
    
    def enable(self, rule_id: str):
        """
        Enable a governance rule
        
        Args:
            rule_id: Rule identifier
        
        Raises:
            KeyError: If rule not found
        """
        if rule_id not in self._enabled:
            raise KeyError(f"Rule not found: {rule_id}")
        
        self._enabled[rule_id] = True
        logger.info(f"Governance rule enabled: {rule_id}")
    
    def disable(self, rule_id: str):
        """
        Disable a governance rule
        
        Args:
            rule_id: Rule identifier
        
        Raises:
            KeyError: If rule not found
        """
        if rule_id not in self._enabled:
            raise KeyError(f"Rule not found: {rule_id}")
        
        self._enabled[rule_id] = False
        logger.info(f"Governance rule disabled: {rule_id}")
    
    def is_enabled(self, rule_id: str) -> bool:
        """
        Check if rule is enabled
        
        Args:
            rule_id: Rule identifier
        
        Returns:
            True if enabled, False otherwise
        """
        return self._enabled.get(rule_id, False)
    
    def get_enabled_rules(self) -> List[GovernanceRule]:
        """
        Get all enabled rules in registration order
        
        Returns:
            List of enabled rules (deterministic order)
        """
        return [
            rule
            for rule in self._rules
            if self._enabled.get(rule.rule_id, False)
        ]
    
    def get_all_rules(self) -> List[GovernanceRule]:
        """
        Get all registered rules
        
        Returns:
            List of all rules
        """
        return list(self._rules)
