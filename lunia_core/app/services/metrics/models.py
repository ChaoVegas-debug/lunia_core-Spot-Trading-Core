"""
Epoch 9.5: DecisionEvent Model — Reconstructible Metrics

Event-sourced model for decision quality metrics.
All metrics derive from immutable DecisionEvents.
"""
from typing import Optional, List, Dict
from datetime import datetime
from pydantic import BaseModel, Field


class DecisionEvent(BaseModel):
    """
    Immutable event representing an Orchestrator decision.
    
    Purpose: Event-sourced foundation for reconstructible metrics
    
    All performance attribution is computed FROM these events,
    never from mutable counters.
    """
    # Identity
    id: str = Field(default_factory=lambda: str(__import__('uuid').uuid4()))
    proposal_id: str = Field(..., description="ExecutionProposal ID")
    
    # Decision
    symbol: str
    side: str  # BUY | SELL | HOLD
    aggregated_confidence: float
    
    # Traceability
    accepted_strategies: List[str] = Field(default_factory=list)
    rejected_strategies: List[Dict[str, str]] = Field(
        default_factory=list,
        description="List of {strategy_id, reason_code, detail}"
    )
    
    # Market Context
    market_state_snapshot: Dict = Field(default_factory=dict)
    
    # Temporal
    created_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + 'Z'
    )
    
    class Config:
        frozen = True  # Immutable


class StrategyPerformanceSnapshot(BaseModel):
    """
    Time-windowed performance metrics for a strategy.
    
    Computed ONLY from DecisionEvents (reconstructible).
    """
    # Identity
    id: str = Field(default_factory=lambda: str(__import__('uuid').uuid4()))
    strategy_id: str
    
    # Window
    window_start: str  # ISO-8601
    window_end: str
    
    # Metrics
    signals_emitted: int = 0
    signals_accepted: int = 0
    acceptance_rate: float = 0.0
    primary_rejection_reason: Optional[str] = None
    avg_confidence: float = 0.0
    
    created_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + 'Z'
    )
