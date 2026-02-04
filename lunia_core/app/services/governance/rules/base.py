"""
EPOCH E Phase E2: Governance Rule Framework
GovernanceRule ABC and RuleResult
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

from pydantic import BaseModel, Field

from ...strategy.models import IntentProposal
from lunia_core.app.services.market_data.realtime.models import MarketSnapshot
from lunia_core.app.services.governance.context import GovernanceContext


class RuleResult(BaseModel):
    """
    Result from a governance rule evaluation
    
    Attributes:
        passed: Whether the rule passed
        reason_code: Machine-readable reason code
        metadata: Additional context (bounded, sanitized)
    """
    passed: bool = Field(..., description="Rule passed or failed")
    reason_code: str = Field(..., description="Machine-readable reason code")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context")


class GovernanceRule(ABC):
    """
    Abstract base class for all governance rules
    
    ALL governance rules must:
    - Inherit from this ABC
    - Implement evaluate()
    - Be deterministic (same input → same output)
    - Be fail-closed (exception → REJECT)
    - Emit machine-readable reason codes
    
    Lifecycle:
    - Rules are registered in GovernanceRuleRegistry
    - Engine evaluates rules in deterministic order
    - First failure short-circuits evaluation
    """
    
    @property
    @abstractmethod
    def rule_id(self) -> str:
        """
        Unique rule identifier
        
        Returns:
            Rule ID (e.g., "market_validity_v1")
        """
        pass
    
    @abstractmethod
    def evaluate(
        self,
        intent: IntentProposal,
        snapshot: MarketSnapshot,
        context: GovernanceContext
    ) -> RuleResult:
        """
        Evaluate governance rule
        
        CRITICAL RULES:
        - MUST be deterministic (same input → same output)
        - MUST be fail-closed (exception → failed RuleResult)
        - MUST NOT mutate inputs
        - MUST NOT have side effects
        
        Args:
            intent: IntentProposal to evaluate
            snapshot: Current market snapshot (read-only)
            context: Governance context (stateful rules may read)
        
        Returns:
            RuleResult (passed, reason_code, metadata)
        """
        pass
