"""
Epoch 9.3: AI Shadow Observer Service

This module provides non-blocking AI commentary on ExecutionProposals.

Architecture:
- Observer receives ExecutionProposal (after Orchestrator decides)
- Dispatches async AI analysis task (zero blocking)
- AI analysis eventually produces AIShadowReport
- Report persisted for human review

CRITICAL INVARIANTS:
1. ZERO blocking: observe() returns immediately (< 0.1ms overhead)
2. ZERO authority: AI comments ONLY, never overrides
3. FAIL-SAFE: AI failures don't affect ExecutionProposal
"""
import asyncio
import logging
import time
from typing import Optional, List

from ..strategy.models import ExecutionProposal
from .models import AIShadowReport, AIRiskAssessment

logger = logging.getLogger(__name__)


class MockAIGateway:
    """
    Mock AI Gateway for testing.
    
    TODO: Replace with real AIGateway when available.
    """
    async def analyze_proposal(
        self,
        proposal: ExecutionProposal,
        market_state: dict
    ) -> dict:
        """
        Mock AI analysis of proposal.
        
        Returns canned response for testing.
        """
        # Simulate AI processing time
        await asyncio.sleep(0.05)  # 50ms mock latency
        
        # Simple mock logic: agree with BUY/SELL, caution on HOLD
        if proposal.side == "HOLD":
            return {
                "agrees": True,
                "risk_assessment": "CAUTION",
                "commentary": (
                    f"Core chose {proposal.side} (confidence={proposal.aggregated_confidence:.2f}). "
                    f"I agree due to {proposal.orchestration_reason_codes}. "
                    f"Market conditions: {market_state.get('market_risk_flag', 'UNKNOWN')}"
                ),
                "alternative_suggestion": None,
                "confidence_score": 0.7
            }
        else:
            return {
                "agrees": True,
                "risk_assessment": "SAFE",
                "commentary": (
                    f"Core chose {proposal.side} based on {len(proposal.target_strategies)} "
                    f"strategies (confidence={proposal.aggregated_confidence:.2f}). "
                    f"I concur with this decision."
                ),
                "alternative_suggestion": None,
                "confidence_score": 0.8
            }


class AIShadowObserver:
    """
    AI Shadow Observer — The Commentator
    
    Observes ExecutionProposals and dispatches async AI commentary.
    
    Features:
    - Zero blocking (async dispatch)
    - Fail-safe (AI failures isolated)
    - Advisory only (no execution authority)
    
    Usage:
        observer = AIShadowObserver()
        observer.observe(proposal)  # Returns immediately
        # Later: AIShadowReport available in storage
    """
    
    def __init__(self, ai_gateway: Optional[MockAIGateway] = None):
        """
        Initialize observer with AI gateway.
        
        Args:
            ai_gateway: AI gateway for analysis (defaults to mock)
        """
        self.ai_gateway = ai_gateway or MockAIGateway()
        self._reports_storage: List[AIShadowReport] = []  # In-memory for now
    
    def observe(self, proposal: ExecutionProposal) -> None:
        """
        Observe proposal and dispatch async AI analysis.
        
        This method returns IMMEDIATELY (zero blocking).
        AI analysis happens asynchronously in background.
        
        Args:
            proposal: ExecutionProposal to analyze
        """
        # Dispatch async task using threading (compatible without event loop)
        try:
            import threading
            thread = threading.Thread(
                target=self._sync_observe_wrapper,
                args=(proposal,),
                daemon=True
            )
            thread.start()
        except Exception as e:
            # Fail-safe: log error but don't crash
            logger.warning(
                f"AI Shadow Observer failed to dispatch thread: {e}",
                extra={"proposal_id": proposal.id}
            )
    
    def _sync_observe_wrapper(self, proposal: ExecutionProposal) -> None:
        """Synchronous wrapper that runs async observe in thread"""
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._async_observe(proposal))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"AI Shadow thread failed: {e}", exc_info=True)
    
    async def _async_observe(self, proposal: ExecutionProposal) -> None:
        """
        Async background task to analyze proposal.
        
        This runs in background, doesn't block caller.
        """
        start_time = time.perf_counter()
        
        try:
            # Call AI gateway
            ai_response = await self.ai_gateway.analyze_proposal(
                proposal=proposal,
                market_state=proposal.market_state_snapshot
            )
            
            # Calculate duration
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            
            # Create report
            report = AIShadowReport(
                proposal_id=proposal.id,
                ai_agrees=ai_response["agrees"],
                ai_risk_assessment=AIRiskAssessment(ai_response["risk_assessment"]),
                ai_commentary=ai_response["commentary"],
                alternative_suggestion=ai_response.get("alternative_suggestion"),
                confidence_score=ai_response.get("confidence_score", 0.5),
                analysis_duration_ms=duration_ms
            )
            
            # Store report (in-memory for now)
            self._reports_storage.append(report)
            
            logger.info(
                f"AI Shadow Report generated: agrees={report.ai_agrees}, "
                f"risk={report.ai_risk_assessment}, duration={duration_ms}ms",
                extra={"proposal_id": proposal.id, "report_id": report.id}
            )
            
        except Exception as e:
            # Fail-safe: log error but don't crash
            logger.error(
                f"AI Shadow analysis failed: {e}",
                extra={"proposal_id": proposal.id},
                exc_info=True
            )
    
    def get_report(self, proposal_id: str) -> Optional[AIShadowReport]:
        """
        Retrieve AI Shadow Report for a proposal.
        
        Args:
            proposal_id: ExecutionProposal ID
        
        Returns:
            AIShadowReport if found, None otherwise
        """
        for report in self._reports_storage:
            if report.proposal_id == proposal_id:
                return report
        return None
    
    def get_all_reports(self) -> List[AIShadowReport]:
        """Get all stored reports"""
        return self._reports_storage.copy()
    
    def clear_reports(self) -> None:
        """Clear all stored reports (for testing)"""
        self._reports_storage.clear()
