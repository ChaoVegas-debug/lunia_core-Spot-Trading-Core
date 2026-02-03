"""
EPOCH E Phase E3: Risk Governance Rules
Governance integration for risk-based blocking (E3.1 UPDATED)
"""
from __future__ import annotations

import logging
# Optional is no longer needed as context_provider is now mandatory

from app.services.governance.rules.base import GovernanceRule, RuleResult
from app.services.governance.context import GovernanceContext
from app.services.strategy.models import IntentProposal
from app.services.market_data.realtime.models import MarketSnapshot

from app.services.risk import RiskEngine, RiskConfig
from app.services.risk.providers import IRiskContextProvider, ProviderErrorCodes


logger = logging.getLogger(__name__)


class RiskGateRule(GovernanceRule):
    """
    Risk Gate Rule - Governance integration for Risk Engine (E3.1 UPDATED)
    
    Responsibilities:
    - Use CompositeRiskContextProvider to build RiskContext (DI)
    - If provider fails (ok=False) → REJECT with GOV_RISK_CONTEXT_UNAVAILABLE
    - Else call RiskEngine.assess()
    - REJECT if !is_safe
    - Inject risk metrics/flags into audit metadata
    
    LOCKED INVARIANTS:
    - Governance remains sole decision maker
    - Risk only provides facts (metrics + flags)
    - Provider errors cannot be bypassed
    - NO PARTIAL CONTEXT (provider enforces)
    """
    
    def __init__(
        self,
        risk_engine: RiskEngine,
        context_provider: IRiskContextProvider
    ):
        """
        Initialize risk gate rule
        
        Args:
            risk_engine: RiskEngine instance
            context_provider: RiskContextProvider (CompositeRiskContextProvider in production)
        """
        self.risk_engine = risk_engine
        self.context_provider = context_provider
        
        logger.info("RiskGateRule initialized with CompositeRiskContextProvider")
    
    @property
    def rule_id(self) -> str:
        return "risk_gate_v1"
    
    def evaluate(
        self,
        intent: IntentProposal,
        snapshot: MarketSnapshot,
        context: GovernanceContext
    ) -> RuleResult:
        """
        Evaluate risk-based governance
        
        Flow:
        1. Call context_provider.build_context()
        2. If !provider_result.ok → REJECT (GOV_RISK_CONTEXT_UNAVAILABLE)
        3. Else call RiskEngine.assess()
        4. If !assessment.is_safe → REJECT (GOV_RISK_BREACH)
        5. Else PASS (include warnings in metadata)
        
        Args:
            intent: IntentProposal
            snapshot: MarketSnapshot
            context: GovernanceContext
        
        Returns:
            RuleResult (passed/failed + reason_code + metadata)
        """
        try:
            # STEP 1: Build RiskContext via provider
            provider_result = self.context_provider.build_context(
                intent,
                snapshot,
                context,
                now_ms=None  # Real-time (in tests, can override)
            )
            
            # STEP 2: Check provider result
            if not provider_result.ok:
                # Provider failed → FAIL-CLOSED
                return RuleResult(
                    passed=False,
                    reason_code=ProviderErrorCodes.GOV_RISK_CONTEXT_UNAVAILABLE,
                    metadata={
                        "blocking_errors": provider_result.blocking_errors,
                        "provider_metadata": provider_result.metadata
                    }
                )
            
            # STEP 3: Assess risk
            assessment = self.risk_engine.assess(intent, provider_result.context)
            
            # STEP 4: Check is_safe
            if not assessment.is_safe:
                return RuleResult(
                    passed=False,
                    reason_code="GOV_RISK_BREACH",
                    metadata={
                        "blocking_flags": assessment.blocking_flags,
                        "warnings": assessment.warnings,
                        "metrics": {k: round(v, 6) for k, v in assessment.metrics.items()},
                        "assumptions": assessment.assumptions,
                        "provider_metadata": provider_result.metadata
                    }
                )
            
            # STEP 5: Passed (include warnings in audit)
            return RuleResult(
                passed=True,
                reason_code="OK",
                metadata={
                    "warnings": assessment.warnings + provider_result.warnings,
                    "metrics": {k: round(v, 6) for k, v in assessment.metrics.items()},
                    "provider_metadata": provider_result.metadata
                }
            )
        
        except Exception as e:
            # Any exception → fail-closed
            logger.error(f"RiskGateRule exception: {e}", exc_info=True)
            return RuleResult(
                passed=False,
                reason_code="GOV_RISK_EXCEPTION",
                metadata={"exception": str(e)}
            )

# The RiskContextProvider and MockRiskContextProvider classes are removed as they are replaced by the new IRiskContextProvider interface and its implementations.
