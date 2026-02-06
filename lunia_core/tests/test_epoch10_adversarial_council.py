"""
Epoch 10: Adversarial Council Tests

Tests deterministic governance rules: VETO, DOWNGRADE, APPROVE.
"""
import pytest

from lunia_core.app.services.strategy.models import ExecutionProposal, SignalSide
from lunia_core.app.services.ai_shadow.models import AIShadowReport, AIRiskAssessment
from lunia_core.app.services.council.models import CouncilDecision, VetoReasonCode
from lunia_core.app.services.council.members import MarketSafetyMember, LiquiditySafetyMember, AIShadowAdvisorMember
from lunia_core.app.services.council.council import AdversarialCouncil
from lunia_core.app.services.council.registry import get_council_members


def create_test_proposal(market_risk="SAFE") -> ExecutionProposal:
    """Create test proposal"""
    return ExecutionProposal(
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        aggregated_confidence=0.8,
        target_strategies=["test"],
        rejected_strategies=[],
        orchestration_reasoning="Test",
        orchestration_reason_codes=["TEST"],
        market_state_snapshot={"market_risk_flag": market_risk}
    )


class TestMarketSafety:
    """Test market safety veto logic"""
    
    def test_dangerous_market_veto(self):
        """DANGEROUS market should VETO"""
        member = MarketSafetyMember()
        proposal = create_test_proposal(market_risk="DANGEROUS")
        
        finding = member.evaluate(proposal)
        
        assert finding.severity == "VETO"
        assert finding.reason_code == VetoReasonCode.DANGEROUS_MARKET.value
        print("✅ Dangerous market → VETO")
    
    def test_safe_market_approve(self):
        """SAFE market should pass"""
        member = MarketSafetyMember()
        proposal = create_test_proposal(market_risk="SAFE")
        
        finding = member.evaluate(proposal)
        
        assert finding.severity == "INFO"
        print("✅ Safe market → INFO")


class TestCouncilEngine:
    """Test council consensus rules"""
    
    def test_veto_consensus(self):
        """ANY VETO → Verdict VETO"""
        council = AdversarialCouncil(members=[MarketSafetyMember()])
        proposal = create_test_proposal(market_risk="DANGEROUS")
        
        verdict = council.review(proposal)
        
        assert verdict.decision == CouncilDecision.VETO
        assert len(verdict.veto_reason_codes) > 0
        assert VetoReasonCode.DANGEROUS_MARKET.value in verdict.veto_reason_codes
        print(f"✅ VETO consensus: {verdict.reasoning}")
    
    def test_downgrade_consensus(self):
        """ANY WARN (no VETO) → DOWNGRADE"""
        # Create AI report with HIGH_RISK
        ai_report = AIShadowReport(
            proposal_id="test",
            ai_agrees=False,
            ai_risk_assessment=AIRiskAssessment.HIGH_RISK,
            ai_commentary="AI flags risk",
            confidence_score=0.9
        )
        
        council = AdversarialCouncil(members=[AIShadowAdvisorMember()])
        proposal = create_test_proposal(market_risk="SAFE")
        
        verdict = council.review(proposal, ai_report=ai_report)
        
        assert verdict.decision == CouncilDecision.DOWNGRADE_TO_HOLD
        print(f"✅ DOWNGRADE consensus: {verdict.reasoning}")
    
    def test_approve_consensus(self):
        """All INFO → APPROVE"""
        council = AdversarialCouncil(members=[MarketSafetyMember()])
        proposal = create_test_proposal(market_risk="SAFE")
        
        verdict = council.review(proposal)
        
        assert verdict.decision == CouncilDecision.APPROVE
        assert len(verdict.veto_reason_codes) == 0
        print(f"✅ APPROVE consensus: {verdict.reasoning}")
    
    def test_determinism(self):
        """Same input → Same verdict"""
        council = AdversarialCouncil(members=get_council_members())
        proposal = create_test_proposal(market_risk="SAFE")
        
        verdict1 = council.review(proposal)
        verdict2 = council.review(proposal)
        
        assert verdict1.decision == verdict2.decision
        assert verdict1.veto_reason_codes == verdict2.veto_reason_codes
        print("✅ Determinism verified")
    
    def test_traceability(self):
        """Verdict contains full vote log"""
        council = AdversarialCouncil(members=get_council_members())
        proposal = create_test_proposal(market_risk="SAFE")
        
        verdict = council.review(proposal)
        
        assert len(verdict.votes) == 4  # 4 members
        for vote in verdict.votes:
            assert "member_id" in vote
            assert "vote" in vote
            assert "reason" in vote
        print(f"✅ Traceability: {len(verdict.votes)} votes logged")


class TestFailSafe:
    """Test fail-safe behavior"""
    
    def test_member_exception_handled(self):
        """Member exception should not crash council"""
        class CrashingMember:
            member_id = "crasher"
            def evaluate(self, *args, **kwargs):
                raise RuntimeError("Test crash")
        
        council = AdversarialCouncil(members=[CrashingMember(), MarketSafetyMember()])
        proposal = create_test_proposal(market_risk="SAFE")
        
        verdict = council.review(proposal)
        
        # Should still produce verdict
        assert verdict is not None
        print("✅ Member exception handled")
