"""
PHASE 10 — PROPOSAL SYSTEM: Integration Layer

Orchestrates proposal lifecycle without modifying Phase 9.x components.

RESPONSIBILITIES:
- Transform strategy intents into proposals
- Handle user decisions (approve/veto)
- Sync execution status from TradeOutcome
"""

from typing import Optional

from extensions.protocol.protocol import StrategyIntent, MarketSnapshot
from extensions.sandbox.paper_types import TradeOutcome
from extensions.proposals.types import ProposalCard, ProposalContext, ProposalStatus
from extensions.proposals.factory import create_proposal
from extensions.proposals.store import ProposalStore
from extensions.proposals.audit import ProposalAuditStore, create_audit_event


# ────────────────────────────────────────────────────────────────────────────────
# INTEGRATION ORCHESTRATOR
# ──────────────────────────────────────────────────────────────────────────────── 


class ProposalIntegration:
    """
    Proposal system integration orchestrator.
    
    Provides high-level API for proposal lifecycle:
    - Creating proposals from strategy intents
    - Recording user decisions
    - Syncing execution status from paper layer
    """
    
    def __init__(self):
        """Initialize integration with isolated stores."""
        self.audit_store = ProposalAuditStore()
        self.store = ProposalStore(self.audit_store)
    
    def on_strategy_intent(
        self,
        intent: StrategyIntent,
        market: MarketSnapshot,
        ctx: ProposalContext,
    ) -> Optional[str]:
        """
        Create proposal from strategy intent.
        
        Args:
            intent: Strategy intent to transform
            market: Market snapshot
            ctx: Proposal context
        
        Returns:
            proposal_id if created, None if not ENTRY intent
        """
        # Create proposal (returns None for non-ENTRY intents)
        proposal = create_proposal(intent, market, ctx)
        
        if proposal is None:
            return None
        
        # Add to store
        self.store.add(proposal)
        
        # Emit audit event
        event = create_audit_event(
            proposal_id=proposal.proposal_id,
            ts_ms=ctx.now_ms,
            actor="SYSTEM",
            event_type="proposal_created",
            old_status=None,
            new_status=ProposalStatus.PENDING,
            reason=f"Created from intent {intent.intent_id}",
            payload={
                "intent_id": intent.intent_id,
                "strategy_id": intent.strategy_id,
                "symbol": intent.symbol,
            },
        )
        self.audit_store.append(event)
        
        return proposal.proposal_id
    
    def on_user_decision(
        self,
        proposal_id: str,
        approve: bool,
        actor: str = "USER",
        now_ms: Optional[int] = None,
    ) -> ProposalCard:
        """
        Record user decision (approve or veto).
        
        Args:
            proposal_id: Proposal ID to decide on
            approve: True to approve, False to veto
            actor: Actor making decision (default "USER")
            now_ms: Current timestamp (injectable)
        
        Returns:
            Updated ProposalCard
        
        Raises:
            ValueError: If proposal not found or invalid state
        """
        if now_ms is None:
            import time
            now_ms = int(time.time() * 1000)
        
        new_status = ProposalStatus.APPROVED if approve else ProposalStatus.VETOED_BY_USER
        reason = "User approved proposal" if approve else "User vetoed proposal"
        
        return self.store.update_status(
            proposal_id=proposal_id,
            new_status=new_status,
            actor=actor,
            reason=reason,
            now_ms=now_ms,
        )
    
    def sync_from_trade_outcome(
        self,
        outcome: TradeOutcome,
        now_ms: Optional[int] = None,
    ) -> Optional[ProposalCard]:
        """
        Sync execution status from TradeOutcome.
        
        Locates proposal by intent_id and marks as EXECUTED if:
        - Proposal status is APPROVED
        - Outcome indicates successful execution
        
        Args:
            outcome: TradeOutcome from paper layer
            now_ms: Current timestamp (injectable)
        
        Returns:
            Updated ProposalCard if found and updated, None otherwise
        """
        if now_ms is None:
            import time
            now_ms = int(time.time() * 1000)
        
        # Find proposal by entry_intent_id
        matching_proposal = None
        for proposal in self.store.list_all():
            if proposal.intent_id == outcome.entry_intent_id:
                matching_proposal = proposal
                break
        
        if matching_proposal is None:
            return None
        
        # Only update if currently APPROVED
        if matching_proposal.status != ProposalStatus.APPROVED:
            return None
        
        # Check if outcome indicates execution (net_pnl != 0 indicates trade occurred)
        if outcome.net_pnl == 0.0 and outcome.fee_total == 0.0:
            # No actual execution occurred
            return None
        
        # Update to EXECUTED
        return self.store.update_status(
            proposal_id=matching_proposal.proposal_id,
            new_status=ProposalStatus.EXECUTED,
            actor="SYSTEM",
            reason=f"Trade executed with outcome {outcome.outcome_id}",
            now_ms=now_ms,
        )
    
    def prune_expired(self, now_ms: Optional[int] = None) -> int:
        """
        Prune expired proposals.
        
        Args:
            now_ms: Current timestamp (injectable)
        
        Returns:
            Number of proposals expired
        """
        if now_ms is None:
            import time
            now_ms = int(time.time() * 1000)
        
        expired = self.store.prune_expired(now_ms)
        return len(expired)
