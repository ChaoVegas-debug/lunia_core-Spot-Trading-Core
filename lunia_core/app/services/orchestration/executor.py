"""
EPOCH E Phase E2.1: Execution Orchestrator
The wiring layer between Governance and Execution
"""
from __future__ import annotations

import logging
from typing import Optional

from lunia_core.app.services.strategy.models import IntentProposal
from lunia_core.app.services.governance.engine import GovernanceEngine
from lunia_core.app.services.governance.models import DecisionType

from .models import ApprovedIntent


logger = logging.getLogger(__name__)


class ExecutionOrchestrator:
    """
    Execution Orchestrator - The Handshake Layer
    
    Responsibilities:
    - Accept IntentProposal from strategies
    - Forward to GovernanceEngine for approval decision
    - Convert APPROVE decisions to ApprovedIntent
    - Forward ApprovedIntent to ExecutionWorker
    - BLOCK all REJECT decisions (no execution)
    
    LOCKED INVARIANTS:
    - SINGLE EXECUTION GATE (ExecutionWorker accepts ONLY ApprovedIntent)
    - NO BYPASS (direct Intent → Worker calls structurally impossible)
    - FAIL-CLOSED (any uncertainty → no execution)
    - EXACTLY-ONCE (idempotency via intent_id)
    - COMPLETE AUDIT TRAIL (Intent ID propagates through all hops)
    
    Architecture:
        IntentProposal
              ↓
        GovernanceEngine.decide()
              ↓
        IF REJECT → STOP (audit + return)
              ↓
        IF APPROVE → build ApprovedIntent
              ↓
        ExecutionWorker.execute_approved()
    """
    
    def __init__(self, governance_engine: GovernanceEngine):
        """
        Initialize execution orchestrator
        
        Args:
            governance_engine: GovernanceEngine instance
        """
        self.governance_engine = governance_engine
        
        logger.info("ExecutionOrchestrator initialized")
    
    def process_intent(self, intent: IntentProposal) -> tuple[bool, str, Optional[ApprovedIntent]]:
        """
        Process intent through governance and prepare for execution
        
        CRITICAL FLOW:
        1. Call GovernanceEngine.decide(intent)
        2. If REJECT → STOP (return rejected status)
        3. If APPROVE → build ApprovedIntent
        4. Return approved intent for execution
        
        Args:
            intent: IntentProposal from strategy
        
        Returns:
            Tuple of (approved: bool, reason: str, approved_intent: Optional[ApprovedIntent])
        """
        # STEP 1: Governance decision
        decision = self.governance_engine.decide(intent)
        
        # STEP 2: Check decision
        if decision.decision == DecisionType.REJECT:
            # REJECT → STOP (no execution)
            logger.info(
                f"Intent REJECTED by governance: {intent.strategy_id} {intent.symbol} "
                f"(reason: {decision.reason_codes})"
            )
            return (False, f"REJECTED: {', '.join(decision.reason_codes)}", None)
        
        # STEP 3: APPROVE → build ApprovedIntent
        approved_intent = ApprovedIntent(
            intent_id=decision.intent_id,
            strategy_id=intent.strategy_id,
            symbol=intent. symbol,
            side=intent.side,
            reference_price=intent.reference_price,
            governance_decision_id=decision.intent_id,  # Audit trail
            rationale=intent.rationale
        )
        
        logger.info(
            f"Intent APPROVED by governance: {intent.strategy_id} {intent.symbol} "
            f"(rules_evaluated: {decision.metadata.get('rules_evaluated', 'unknown')})"
        )
        
        return (True, "APPROVED", approved_intent)
