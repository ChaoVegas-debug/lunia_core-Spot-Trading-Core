"""
Epoch 9.3: AI Shadow Observer Tests

Test Coverage:
1. Async Handoff (< 1ms blocking)
2. Persistence (Report eventually saved)
3. Linkage (Correct proposal association)
4. Fail-Safe (AI failures isolated)
"""
import time
import pytest
from typing import Optional

from lunia_core.app.services.ai_shadow.observer import AIShadowObserver, MockAIGateway
from lunia_core.app.services.ai_shadow.models import AIShadowReport, AIRiskAssessment
from lunia_core.app.services.strategy.models import ExecutionProposal, SignalSide


def create_test_proposal(side: SignalSide = SignalSide.BUY) -> ExecutionProposal:
    """Create minimal test proposal"""
    return ExecutionProposal(
        symbol="BTC/USDT",
        side=side,
        aggregated_confidence=0.8,
        target_strategies=["test-strategy-1"],
        rejected_strategies=[],
        orchestration_reasoning="Test",
        orchestration_reason_codes=["TEST"],
        market_state_snapshot={"market_risk_flag": "SAFE"}
    )


class TestAsyncHandoff:
    """Test that observe() returns immediately"""
    
    def test_observe_returns_immediately(self):
        """observe() should return in < 1ms"""
        observer = AIShadowObserver()
        proposal = create_test_proposal()
        
        start = time.perf_counter()
        observer.observe(proposal)
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        assert elapsed_ms < 1.0, f"observe() took {elapsed_ms:.2f}ms"
        print(f"✅ observe() returned in {elapsed_ms:.3f}ms")
    
    def test_multiple_observations_parallel(self):
        """Multiple observe() calls should not block"""
        observer = AIShadowObserver()
        proposals = [create_test_proposal() for _ in range(10)]
        
        start = time.perf_counter()
        for proposal in proposals:
            observer.observe(proposal)
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        assert elapsed_ms < 5.0, f"10 observations took {elapsed_ms:.2f}ms"
        print(f"✅ 10 observations in {elapsed_ms:.2f}ms")


class TestPersistence:
    """Test that Report is eventually persisted"""
    
    def test_report_eventually_persisted(self):
        """Report should be available eventually"""
        observer = AIShadowObserver()
        proposal = create_test_proposal()
        
        observer.observe(proposal)
        
        # Wait for async processing
        report = None
        for _ in range(30):  # 300ms max
            time.sleep(0.01)
            report = observer.get_report(proposal.id)
            if report:
                break
        
        assert report is not None, "Report not found after 300ms"
        assert report.proposal_id == proposal.id
        print(f"✅ Report persisted")
    
    def test_report_contains_required_fields(self):
        """Report should have all required fields"""
        observer = AIShadowObserver()
        proposal = create_test_proposal()
        
        observer.observe(proposal)
        time.sleep(0.15)
        
        report = observer.get_report(proposal.id)
        assert report is not None
        assert isinstance(report.ai_agrees, bool)
        assert report.ai_risk_assessment in ["SAFE", "CAUTION", "HIGH_RISK"]
        assert len(report.ai_commentary) > 0
        assert 0.0 <= report.confidence_score <= 1.0
        print(f"✅ All fields present")


class TestLinkage:
    """Test correct proposal linkage"""
    
    def test_report_proposal_linkage(self):
        """Report should link to correct proposal"""
        observer = AIShadowObserver()
        
        proposal1 = create_test_proposal(side=SignalSide.BUY)
        proposal2 = create_test_proposal(side=SignalSide.SELL)
        
        observer.observe(proposal1)
        observer.observe(proposal2)
        time.sleep(0.2)
        
        report1 = observer.get_report(proposal1.id)
        report2 = observer.get_report(proposal2.id)
        
        assert report1 is not None and report2 is not None
        assert report1.proposal_id == proposal1.id
        assert report2.proposal_id == proposal2.id
        print(f"✅ Linkage verified")
    
    def test_get_all_reports(self):
        """get_all_reports() should return all reports"""
        observer = AIShadowObserver()
        
        proposals = [create_test_proposal() for _ in range(3)]
        for proposal in proposals:
            observer.observe(proposal)
        
        time.sleep(0.25)
        
        all_reports = observer.get_all_reports()
        assert len(all_reports) >= 3
        print(f"✅ get_all_reports() returned {len(all_reports)} reports")


class FailingAIGateway:
    """Mock gateway that always fails"""
    async def analyze_proposal(self, proposal, market_state):
        raise RuntimeError("Mock AI failure")


class TestFailSafe:
    """Test that AI failures don't affect Proposal"""
    
    def test_ai_failure_doesnt_crash(self):
        """AI failure should be isolated"""
        observer = AIShadowObserver(ai_gateway=FailingAIGateway())
        proposal = create_test_proposal()
        
        try:
            observer.observe(proposal)
            success = True
        except:
            success = False
        
        assert success, "observe() should not raise exception"
        print("✅ AI failure isolated")
    
    def test_ai_failure_no_report_created(self):
        """AI failure should not create report"""
        observer = AIShadowObserver(ai_gateway=FailingAIGateway())
        proposal = create_test_proposal()
        
        observer.observe(proposal)
        time.sleep(0.15)
        
        report = observer.get_report(proposal.id)
        assert report is None, "Report should not exist after AI failure"
        print("✅ AI failure → no report")
    
    def test_proposal_remains_unchanged(self):
        """Proposal should remain unchanged"""
        observer = AIShadowObserver()
        proposal = create_test_proposal()
        
        original_id = proposal.id
        original_side = proposal.side
        
        observer.observe(proposal)
        
        assert proposal.id == original_id
        assert proposal.side == original_side
        print("✅ Proposal immutable")


class TestAIAnalysisQuality:
    """Test AI analysis quality"""
    
    def test_ai_commentary_non_empty(self):
        """AI should provide commentary"""
        observer = AIShadowObserver()
        proposal = create_test_proposal()
        
        observer.observe(proposal)
        time.sleep(0.15)
        
        report = observer.get_report(proposal.id)
        assert report is not None
        assert len(report.ai_commentary) > 10
        print(f"✅ Commentary: {len(report.ai_commentary)} chars")
    
    def test_analysis_duration_tracked(self):
        """Analysis duration should be tracked"""
        observer = AIShadowObserver()
        proposal = create_test_proposal()
        
        observer.observe(proposal)
        time.sleep(0.2)
        
        report = observer.get_report(proposal.id)
        assert report is not None
        assert report.analysis_duration_ms is not None
        assert report.analysis_duration_ms > 0
        print(f"✅ Analysis took {report.analysis_duration_ms}ms")
