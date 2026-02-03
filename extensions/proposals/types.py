"""
PHASE 10 — PROPOSAL SYSTEM: Core Types

Immutable UI contract for human-in-the-loop proposal cards.

DESIGN PRINCIPLES:
- Frozen dataclasses (immutable after creation)
- JSON-serializable primitives only
- No dependencies on Phase 9.x internal state
- Deterministic identity (sha256-based IDs)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any


# ────────────────────────────────────────────────────────────────────────────────
# ENUMS
# ────────────────────────────────────────────────────────────────────────────────


class ProposalStatus(Enum):
    """Proposal lifecycle states with strict transition rules."""
    PENDING = "pending"  # Initial state: awaiting human decision
    APPROVED = "approved"  # User approved: ready for execution
    VETOED_BY_USER = "vetoed_by_user"  # User rejected: terminal
    REJECTED_BY_RISK = "rejected_by_risk"  # Risk engine rejected: terminal
    EXPIRED = "expired"  # TTL exceeded: terminal
    EXECUTED = "executed"  # Trade executed (synced from paper layer): terminal
    ARCHIVED = "archived"  # Moved to archive (policy-based): terminal


# ────────────────────────────────────────────────────────────────────────────────
# PROPOSAL CARD (UI CONTRACT)
# ────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ProposalCard:
    """
    Immutable proposal card for UI rendering.
    
    Represents a frozen snapshot of a strategy intent transformed into
    human-readable format with risk visualization and lifecycle tracking.
    """
    
    # ─── Identity ───
    proposal_id: str  # 16-hex deterministic (sha256 of core fields)
    intent_id: str  # From StrategyIntent
    run_id: str  # From GovernanceContext
    correlation_id: str  # From GovernanceContext
    strategy_id: str  # From StrategyIntent
    
    # ─── Display / Humanization ───
    strategy_name: str  # Human-readable strategy name
    symbol: str  # Trading symbol (e.g., "BTC/USD")
    side_pretty: str  # "BUY" or "SELL"
    side_style: str  # "success" (buy/long) or "danger" (sell/short)
    size_pretty: str  # Human-readable size (e.g., "0.5 BTC")
    
    # ─── Explanation ───
    rationale_text: str  # Plain text rationale (50-500 chars recommended)
    rationale_sections: List[Dict[str, str]]  # Structured rationale with stable ordering
    
    # ─── Risk Visualization ───
    risk_metrics: Dict[str, float]  # REQUIRED: implied_loss_pct, reward_to_risk, max_loss_quote
    exit_plan_view: Dict[str, Any]  # Derived from TradeExitPlan (stop_loss_price, take_profit_price, time_limit_ms, time_limit_human)
    
    # ─── Lifecycle ───
    status: ProposalStatus
    created_at_ms: int  # Proposal creation timestamp
    expires_at_ms: int  # Proposal expiry timestamp
    decided_at_ms: Optional[int]  # When user decision was made
    decided_by: Optional[str]  # Actor who made decision (e.g., "USER", "RISK_ENGINE")
    executed_at_ms: Optional[int]  # When trade was executed (synced from paper layer)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to JSON-serializable dict.
        
        Returns dict with primitive types only (str, int, float, bool, list, dict, None).
        """
        return {
            "proposal_id": self.proposal_id,
            "intent_id": self.intent_id,
            "run_id": self.run_id,
            "correlation_id": self.correlation_id,
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "symbol": self.symbol,
            "side_pretty": self.side_pretty,
            "side_style": self.side_style,
            "size_pretty": self.size_pretty,
            "rationale_text": self.rationale_text,
            "rationale_sections": self.rationale_sections,
            "risk_metrics": self.risk_metrics,
            "exit_plan_view": self.exit_plan_view,
            "status": self.status.value,
            "created_at_ms": self.created_at_ms,
            "expires_at_ms": self.expires_at_ms,
            "decided_at_ms": self.decided_at_ms,
            "decided_by": self.decided_by,
            "executed_at_ms": self.executed_at_ms,
        }


# ────────────────────────────────────────────────────────────────────────────────
# PROPOSAL CONTEXT (FACTORY INPUT)
# ────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ProposalContext:
    """
    Context for proposal creation (injectable dependencies).
    
    Provides runtime context and configuration for transforming
    StrategyIntent into ProposalCard.
    """
    strategy_id: str
    strategy_name: str  # Human-friendly name
    run_id: str
    correlation_id: str
    governance_snapshot: Optional[Dict[str, Any]]  # Minimal governance state (JSON-safe)
    now_ms: int  # Injectable timestamp for deterministic testing
