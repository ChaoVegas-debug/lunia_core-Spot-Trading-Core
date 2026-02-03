"""
PHASE 10 — PROPOSAL SYSTEM: State Machine Store

In-memory proposal storage with strict lifecycle enforcement.

STATE MACHINE:
- PENDING → APPROVED | VETOED_BY_USER | REJECTED_BY_RISK | EXPIRED
- APPROVED → EXECUTED (only via TradeOutcome sync)
- Terminal states → ARCHIVED (policy-based)
"""

from typing import Dict, Optional, List
from collections import OrderedDict

from extensions.proposals.types import ProposalCard, ProposalStatus
from extensions.proposals.audit import ProposalAuditStore, create_audit_event


# ────────────────────────────────────────────────────────────────────────────────
# STATE MACHINE RULES
# ────────────────────────────────────────────────────────────────────────────────

VALID_TRANSITIONS = {
    ProposalStatus.PENDING: {
        ProposalStatus.APPROVED,
        ProposalStatus.VETOED_BY_USER,
        ProposalStatus.REJECTED_BY_RISK,
        ProposalStatus.EXPIRED,
    },
    ProposalStatus.APPROVED: {
        ProposalStatus.EXECUTED,
    },
    # Terminal states can move to ARCHIVED
    ProposalStatus.VETOED_BY_USER: {ProposalStatus.ARCHIVED},
    ProposalStatus.REJECTED_BY_RISK: {ProposalStatus.ARCHIVED},
    ProposalStatus.EXPIRED: {ProposalStatus.ARCHIVED},
    ProposalStatus.EXECUTED: {ProposalStatus.ARCHIVED},
    # ARCHIVED is final
    ProposalStatus.ARCHIVED: set(),
}


# ────────────────────────────────────────────────────────────────────────────────
# PROPOSAL STORE
# ────────────────────────────────────────────────────────────────────────────────


class ProposalStore:
    """
    In-memory proposal storage with state machine enforcement.
    
    Maintains proposals in OrderedDict for stable iteration order.
    Emits audit events for all state changes.
    """
    
    def __init__(self, audit_store: ProposalAuditStore):
        """
        Initialize proposal store.
        
        Args:
            audit_store: ProposalAuditStore for audit trail
        """
        self._proposals: OrderedDict[str, ProposalCard] = OrderedDict()
        self._audit_store = audit_store
    
    def add(self, proposal: ProposalCard) -> None:
        """
        Add new proposal to store.
        
        Args:
            proposal: ProposalCard to add
        """
        self._proposals[proposal.proposal_id] = proposal
    
    def get(self, proposal_id: str) -> Optional[ProposalCard]:
        """
        Get proposal by ID.
        
        Args:
            proposal_id: Proposal ID to lookup
        
        Returns:
            ProposalCard if found, None otherwise
        """
        return self._proposals.get(proposal_id)
    
    def list_all(self) -> List[ProposalCard]:
        """
        List all proposals (chronological order).
        
        Returns:
            List of ProposalCards
        """
        return list(self._proposals.values())
    
    def list_by_status(self, status: ProposalStatus) -> List[ProposalCard]:
        """
        List proposals by status.
        
        Args:
            status: ProposalStatus to filter by
        
        Returns:
            List of ProposalCards with matching status
        """
        return [p for p in self._proposals.values() if p.status == status]
    
    def update_status(
        self,
        proposal_id: str,
        new_status: ProposalStatus,
        actor: str,
        reason: Optional[str],
        now_ms: int,
    ) -> ProposalCard:
        """
        Update proposal status with state machine validation.
        
        Args:
            proposal_id: Proposal ID to update
            new_status: New status
            actor: Actor performing update
            reason: Reason for update
            now_ms: Current timestamp
        
        Returns:
            Updated ProposalCard
        
        Raises:
            ValueError: If proposal not found or invalid transition
        """
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal not found: {proposal_id}")
        
        old_status = proposal.status
        
        # Validate transition
        if new_status not in VALID_TRANSITIONS.get(old_status, set()):
            raise ValueError(
                f"Invalid transition: {old_status.value} → {new_status.value}"
            )
        
        # Create updated proposal (frozen dataclass → replace)
        updated_proposal = ProposalCard(
            proposal_id=proposal.proposal_id,
            intent_id=proposal.intent_id,
            run_id=proposal.run_id,
            correlation_id=proposal.correlation_id,
            strategy_id=proposal.strategy_id,
            strategy_name=proposal.strategy_name,
            symbol=proposal.symbol,
            side_pretty=proposal.side_pretty,
            side_style=proposal.side_style,
            size_pretty=proposal.size_pretty,
            rationale_text=proposal.rationale_text,
            rationale_sections=proposal.rationale_sections,
            risk_metrics=proposal.risk_metrics,
            exit_plan_view=proposal.exit_plan_view,
            status=new_status,
            created_at_ms=proposal.created_at_ms,
            expires_at_ms=proposal.expires_at_ms,
            decided_at_ms=now_ms if old_status == ProposalStatus.PENDING else proposal.decided_at_ms,
            decided_by=actor if old_status == ProposalStatus.PENDING else proposal.decided_by,
            executed_at_ms=now_ms if new_status == ProposalStatus.EXECUTED else proposal.executed_at_ms,
        )
        
        # Update store
        self._proposals[proposal_id] = updated_proposal
        
        # Emit audit event
        event = create_audit_event(
            proposal_id=proposal_id,
            ts_ms=now_ms,
            actor=actor,
            event_type="status_changed",
            old_status=old_status,
            new_status=new_status,
            reason=reason,
            payload={"proposal_id": proposal_id},
        )
        self._audit_store.append(event)
        
        return updated_proposal
    
    def prune_expired(self, now_ms: int) -> List[ProposalCard]:
        """
        Move expired PENDING proposals to EXPIRED status.
        
        Args:
            now_ms: Current timestamp
        
        Returns:
            List of expired ProposalCards
        """
        expired_proposals = []
        
        for proposal in self.list_by_status(ProposalStatus.PENDING):           
            if proposal.expires_at_ms <= now_ms:
                updated = self.update_status(
                    proposal_id=proposal.proposal_id,
                    new_status=ProposalStatus.EXPIRED,
                    actor="SYSTEM",
                    reason=f"TTL exceeded at {now_ms}",
                    now_ms=now_ms,
                )
                expired_proposals.append(updated)
        
        return expired_proposals
    
    def count(self) -> int:
        """Return total number of proposals."""
        return len(self._proposals)
