"""
Epoch 10: Council Members — The Adversaries

Protocol-compliant council members that evaluate proposals.
Each member implements deterministic governance rules.
"""
from typing import Protocol, Optional
import logging

from ..strategy.models import ExecutionProposal
from ..ai_shadow.models import AIShadowReport
from ..metrics.models import StrategyPerformanceSnapshot
from .models import CouncilFinding, VetoReasonCode

logger = logging.getLogger(__name__)


class CouncilMember(Protocol):
    """Protocol for all council members"""
    member_id: str
    
    def evaluate(
        self,
        proposal: ExecutionProposal,
        ai_report: Optional[AIShadowReport],
        metrics: Optional[StrategyPerformanceSnapshot]
    ) -> CouncilFinding:
        """Evaluate proposal and return finding"""
        ...


class MarketSafetyMember:
    """Vetos if market_risk_flag == DANGEROUS"""
    
    member_id = "market_safety"
    
    def evaluate(self, proposal, ai_report=None, metrics=None) -> CouncilFinding:
        market_risk = proposal.market_state_snapshot.get("market_risk_flag", "UNKNOWN")
        
        if market_risk == "DANGEROUS":
            return CouncilFinding(
                member_id=self.member_id,
                severity="VETO",
                reason_code=VetoReasonCode.DANGEROUS_MARKET.value,
                message=f"Market risk flag is DANGEROUS (proposal side={proposal.side})"
            )
        elif market_risk == "RISKY":
            return CouncilFinding(
                member_id=self.member_id,
                severity="WARN",
                reason_code=VetoReasonCode.DANGEROUS_MARKET.value,
                message="Market risk flag is RISKY (proceed with caution)"
            )
        else:
            return CouncilFinding(
                member_id=self.member_id,
                severity="INFO",
                reason_code="MARKET_SAFE",
                message=f"Market risk acceptable ({market_risk})"
            )


class LiquiditySafetyMember:
    """Vetos if liquidity_stress == CRITICAL"""
    
    member_id = "liquidity_safety"
    
    def evaluate(self, proposal, ai_report=None, metrics=None) -> CouncilFinding:
        liquidity_stress = proposal.market_state_snapshot.get("liquidity", {}).get("liquidity_stress", "UNKNOWN")
        
        if liquidity_stress == "CRITICAL":
            return CouncilFinding(
                member_id=self.member_id,
                severity="VETO",
                reason_code=VetoReasonCode.LIQUIDITY_CRISIS.value,
                message="Liquidity stress is CRITICAL (cannot execute safely)"
            )
        elif liquidity_stress == "HIGH":
            return CouncilFinding(
                member_id=self.member_id,
                severity="WARN",
                reason_code=VetoReasonCode.LIQUIDITY_CRISIS.value,
                message="Liquidity stress is HIGH (downgrade recommended)"
            )
        else:
            return CouncilFinding(
                member_id=self.member_id,
                severity="INFO",
                reason_code="LIQUIDITY_OK",
                message=f"Liquidity acceptable ({liquidity_stress})"
            )


class MetricsGuardMember:
    """Warns if strategy metrics show degradation"""
    
    member_id = "metrics_guard"
    
    def __init__(self, min_acceptance_rate: float = 0.5):
        self.min_acceptance_rate = min_acceptance_rate
    
    def evaluate(self, proposal, ai_report=None, metrics=None) -> CouncilFinding:
        if metrics is None:
            return CouncilFinding(
                member_id=self.member_id,
                severity="INFO",
                reason_code="NO_METRICS",
                message="No metrics available (cold-start)"
            )
        
        if metrics.acceptance_rate < self.min_acceptance_rate:
            return CouncilFinding(
                member_id=self.member_id,
                severity="WARN",
                reason_code=VetoReasonCode.METRICS_DEGRADATION.value,
                message=f"Strategy acceptance rate low ({metrics.acceptance_rate:.2%} < {self.min_acceptance_rate:.2%})"
            )
        else:
            return CouncilFinding(
                member_id=self.member_id,
                severity="INFO",
                reason_code="METRICS_OK",
                message=f"Strategy metrics healthy ({metrics.acceptance_rate:.2%})"
            )


class AIShadowAdvisorMember:
    """
    Warns (not vetos) if AI flags HIGH_RISK.
    
    AI CANNOT veto alone - only provide advisory input.
    """
    
    member_id = "ai_shadow_advisor"
    
    def evaluate(self, proposal, ai_report=None, metrics=None) -> CouncilFinding:
        if ai_report is None:
            return CouncilFinding(
                member_id=self.member_id,
                severity="INFO",
                reason_code="NO_AI_REPORT",
                message="No AI report available"
            )
        
        # AI flagged HIGH_RISK + high confidence → WARN (not VETO)
        if ai_report.ai_risk_assessment == "HIGH_RISK" and ai_report.confidence_score > 0.7:
            return CouncilFinding(
                member_id=self.member_id,
                severity="WARN",
                reason_code=VetoReasonCode.AI_RISK_FLAG.value,
                message=f"AI flags HIGH_RISK (confidence={ai_report.confidence_score:.2f}): {ai_report.ai_commentary[:100]}"
          )
        else:
            return CouncilFinding(
                member_id=self.member_id,
                severity="INFO",
                reason_code="AI_NEUTRAL",
                message=f"AI assessment: {ai_report.ai_risk_assessment}"
            )
