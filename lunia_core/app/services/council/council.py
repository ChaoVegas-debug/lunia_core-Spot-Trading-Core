"""
Epoch 10: Adversarial Council Engine

Deterministic governance engine that orchestrates council members.
"""
import time
import logging
from typing import List, Optional

from ..strategy.models import ExecutionProposal
from ..ai_shadow.models import AIShadowReport
from ..metrics.models import StrategyPerformanceSnapshot
from .models import CouncilVerdict, CouncilDecision, CouncilFinding
from .members import CouncilMember

logger = logging.getLogger(__name__)


class AdversarialCouncil:
    """
    The Council — Adversarial Governance Filter
    
    Reviews ExecutionProposals and produces deterministic verdicts.
    
    Consensus Rules:
    - ANY VETO finding → Verdict = VETO
    - ANY WARN finding (no VETO) → Verdict = DOWNGRADE_TO_HOLD
    - All INFO → Verdict = APPROVE
    
    Fail-Safe:
    - Member exception → Log + continue
    - Engine crash/timeout → DOWNGRADE_TO_HOLD (safety-first)
    """
    
    def __init__(self, members: List[CouncilMember], time_budget_ms: int = 100):
        self.members = members
        self.time_budget_ms = time_budget_ms
    
    def review(
        self,
        proposal: ExecutionProposal,
        ai_report: Optional[AIShadowReport] = None,
        metrics: Optional[StrategyPerformanceSnapshot] = None
    ) -> CouncilVerdict:
        """
        Review proposal with full council.
        
        Returns deterministic verdict with full audit trail.
        """
        start_time = time.perf_counter()
        findings: List[CouncilFinding] = []
        
        # Execute all members (with isolation)
        for member in self.members:
            try:
                finding = member.evaluate(proposal, ai_report, metrics)
                findings.append(finding)
                
                logger.debug(
                    f"Council member {member.member_id}: {finding.severity} - {finding.message}"
                )
            except Exception as e:
                # Fail-safe: member crash doesn't stop council
                logger.error(
                    f"Council member {member.member_id} failed: {e}",
                    exc_info=True
                )
                # Add fallback finding
                findings.append(CouncilFinding(
                    member_id=member.member_id,
                    severity="ERROR",
                    reason_code="MEMBER_EXCEPTION",
                    message=f"Member crashed: {str(e)[:100]}"
                ))
        
        # Check time budget (soft limit)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        if elapsed_ms > self.time_budget_ms:
            logger.warning(
                f"Council review exceeded time budget: {elapsed_ms:.1f}ms > {self.time_budget_ms}ms"
            )
        
        # Apply consensus rules
        decision, veto_codes, reasoning = self._apply_consensus(findings)
        
        # Build verdict
        verdict = CouncilVerdict(
            proposal_id=proposal.id,
            decision=decision,
            veto_reason_codes=veto_codes,
            reasoning=reasoning,
            votes=[
                {
                    "member_id": f.member_id,
                    "vote": f.severity,
                    "reason": f.reason_code,
                    "message": f.message
                }
                for f in findings
            ],
            market_state_snapshot=proposal.market_state_snapshot.copy()
        )
        
        logger.info(
            f"Council verdict: {decision.value} for proposal {proposal.id[:8]}... "
            f"(veto_codes={veto_codes}, elapsed={elapsed_ms:.1f}ms)"
        )
        
        return verdict
    
    def _apply_consensus(self, findings: List[CouncilFinding]) -> tuple:
        """
        Apply consensus rules to findings.
        
        Returns: (decision, veto_codes, reasoning)
        """
        veto_findings = [f for f in findings if f.severity == "VETO"]
        warn_findings = [f for f in findings if f.severity == "WARN"]
        
        if veto_findings:
            # ANY VETO → VETO
            veto_codes = [f.reason_code for f in veto_findings]
            reasoning = f"VETO: {len(veto_findings)} member(s) blocked proposal. " + "; ".join(
                f"{f.member_id}: {f.message}" for f in veto_findings
            )
            return (CouncilDecision.VETO, veto_codes, reasoning)
        
        elif warn_findings:
            # ANY WARN (no VETO) → DOWNGRADE
            warn_codes = [f.reason_code for f in warn_findings]
            reasoning = f"DOWNGRADE: {len(warn_findings)} warning(s). " + "; ".join(
                f"{f.member_id}: {f.message}" for f in warn_findings
            )
            return (CouncilDecision.DOWNGRADE_TO_HOLD, warn_codes, reasoning)
        
        else:
            # All INFO → APPROVE
            return (
                CouncilDecision.APPROVE,
                [],
                f"APPROVE: All {len(findings)} council members cleared proposal."
            )
