"""
EPOCH E Phase E2: Governance Engine
The single decision authority with fail-closed semantics
"""
from __future__ import annotations

import logging
from typing import List, Optional

from app.services.market_data.realtime.synchronous import ThreadSafeSnapshotCache
from app.services.market_data.realtime.models import MarketSnapshot, SnapshotState
from app.services.strategy.models import IntentProposal

from .models import GovernanceDecision, DecisionType
from .context import GovernanceContext
from .rules.base import GovernanceRule
from .registry import GovernanceRuleRegistry


logger = logging.getLogger(__name__)


class GovernanceEngine:
    """
    Governance Engine - The Single Decision Authority
    
    Responsibilities:
    - Receive IntentProposals
    - Evaluate against explicit governance rules
    - Produce GovernanceDecisions (APPROVE/REJECT)
    - Maintain internal state for stateful rules
    - Emit complete audit trail
    
    LOCKED INVARIANTS:
    - GOVERNANCE PRIMACY (final veto power, no bypass)
    - FAIL-CLOSED BY DEFAULT (any failure → REJECT)
    - READ-ONLY INPUTS (no mutations)
    - RULE-BASED (deterministic, no heuristics)
    - AUDIT FIRST (every decision emits reason_codes)
    - STATEFUL GOVERNANCE (explicit, deterministic)
    
    Architecture:
        IntentProposal
              ↓
        Load MarketSnapshot (read-only)
              ↓
        Evaluate Rules (short-circuit on first failure)
              ↓
        Update GovernanceContext (ONLY on APPROVE)
              ↓
        Emit GovernanceDecision
    """
    
    def __init__(
        self,
        snapshot_cache: ThreadSafeSnapshotCache,
        rule_registry: GovernanceRuleRegistry,
        context: Optional[GovernanceContext] = None
    ):
        """
        Initialize governance engine
        
        Args:
            snapshot_cache: Thread-safe snapshot cache (read-only)
            rule_registry: Governance rule registry
            context: Governance context (defaults to new instance)
        """
        self.snapshot_cache = snapshot_cache
        self.rule_registry = rule_registry
        self.context = context or GovernanceContext()
        
        logger.info("GovernanceEngine initialized")
    
    def decide(self, intent: IntentProposal) -> GovernanceDecision:
        """
        Make governance decision on IntentProposal
        
        CRITICAL FLOW (STRICT ORDER):
        1. Load market snapshot (read-only, O(1))
        2. Evaluate rules in deterministic order
        3. Short-circuit on first failure
        4. Update context ONLY on APPROVE
        5. Emit GovernanceDecision
        
        Args:
            intent: IntentProposal to evaluate
        
        Returns:
            GovernanceDecision (APPROVE or REJECT with reason_codes)
        """
        # STEP 1: Load market snapshot (fail-closed if missing)
        snapshot = self.snapshot_cache.get(intent.symbol)
        
        if snapshot is None:
            return GovernanceDecision(
                intent_id=self._generate_intent_id(intent),
                strategy_id=intent.strategy_id,
                symbol=intent.symbol,
                decision=DecisionType.REJECT,
                reason_codes=["GOV_NO_SNAPSHOT"],
                metadata={"reason": "Market snapshot not available"}
            )
        
        # STEP 2: Evaluate rules in deterministic order (short-circuit)
        enabled_rules = self.rule_registry.get_enabled_rules()
        
        for rule in enabled_rules:
            try:
                result = rule.evaluate(intent, snapshot, self.context)
                
                if not result.passed:
                    # Rule failed → REJECT (short-circuit)
                    return GovernanceDecision(
                        intent_id=self._generate_intent_id(intent),
                        strategy_id=intent.strategy_id,
                        symbol=intent.symbol,
                        decision=DecisionType.REJECT,
                        reason_codes=[result.reason_code],
                        metadata={
                            "rule_id": rule.rule_id,
                            "rule_metadata": result.metadata
                        }
                    )
            
            except Exception as e:
                # Rule exception → REJECT (fail-closed)
                logger.error(f"Governance rule exception: {rule.rule_id}: {e}", exc_info=True)
                
                return GovernanceDecision(
                    intent_id=self._generate_intent_id(intent),
                    strategy_id=intent.strategy_id,
                    symbol=intent.symbol,
                    decision=DecisionType.REJECT,
                    reason_codes=["GOV_RULE_EXCEPTION"],
                    metadata={
                        "rule_id": rule.rule_id,
                        "exception": str(e)
                    }
                )
        
        # STEP 3: All rules passed → APPROVE
        # Update context (stateful rules may need this)
        self.context.record_execution(intent.strategy_id, intent.symbol)
        
        return GovernanceDecision(
            intent_id=self._generate_intent_id(intent),
            strategy_id=intent.strategy_id,
            symbol=intent.symbol,
            decision=DecisionType.APPROVE,
            reason_codes=["APPROVED"],
            metadata={"rules_evaluated": len(enabled_rules)}
        )
    
    def decide_batch(self, intents: List[IntentProposal]) -> List[GovernanceDecision]:
        """
        Make governance decisions on multiple intents
        
        Args:
            intents: List of IntentProposals
        
        Returns:
            List of GovernanceDecisions (same order as inputs)
        """
        return [self.decide(intent) for intent in intents]
    
    def get_context(self) -> GovernanceContext:
        """
        Get governance context (for debugging/auditing)
        
        Returns:
            GovernanceContext instance
        """
        return self.context
    
    def reset_context(self):
        """
        Reset governance context (for testing or manual intervention)
        """
        self.context.reset()
        logger.info("Governance context reset")
    
    def _generate_intent_id(self, intent: IntentProposal) -> str:
        """
        Generate intent ID for cross-reference
        
        Args:
            intent: IntentProposal
        
        Returns:
            Intent ID (strategy_id + symbol + created_at_ms)
        """
        return f"{intent.strategy_id}_{intent.symbol}_{intent.created_at_ms}"
