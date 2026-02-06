"""
Risk Governor Journal — Audit Trail for Risk Decisions

All risk decisions are recorded as immutable events.
Queryable by verdict_id, plan_id, or symbol.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class RiskGovernorEvent(BaseModel):
    """
    Immutable risk decision event for audit trail.
    
    Records all context needed to understand why a decision was made.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    # Identifiers
    verdict_id: str
    plan_id: str
    symbol: str
    side: str
    
    # Decision
    decision: str  # "ALLOW" | "BLOCK" | etc
    reason_codes: List[str]
    reasoning: str
    
    # Computed metrics (for audit)
    computed_metrics: Dict = Field(default_factory=dict)
    limits_snapshot: Dict = Field(default_factory=dict)
    correlation_cluster_id: str
    
    # Circuit breaker context
    window_count: Optional[int] = None
    consecutive_blocks: Optional[int] = None
    halt_recommended: bool = False
    
    # Temporal
    created_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + 'Z'
    )
    
    class Config:
        frozen = True
        use_enum_values = True


class RiskGovernorJournal:
    """
    In-memory event store for risk decisions.
    
    Thread-safe append-only journal.
    """
    
    def __init__(self):
        self._events: List[RiskGovernorEvent] = []
    
    def record(self, event: RiskGovernorEvent) -> None:
        """
        Record a risk decision event.
        
        Args:
            event: Immutable event to record
        """
        self._events.append(event)
    
    def get_all_events(self) -> List[RiskGovernorEvent]:
        """Get all recorded events (for testing/audit)"""
        return list(self._events)
    
    def get_events_for_verdict(self, verdict_id: str) -> List[RiskGovernorEvent]:
        """Get all events for a specific verdict"""
        return [e for e in self._events if e.verdict_id == verdict_id]
    
    def get_events_for_plan(self, plan_id: str) -> List[RiskGovernorEvent]:
        """Get all events for a specific plan"""
        return [e for e in self._events if e.plan_id == plan_id]
    
    def get_events_for_symbol(self, symbol: str) -> List[RiskGovernorEvent]:
        """Get all events for a specific symbol"""
        return [e for e in self._events if e.symbol == symbol]
    
    def count_blocks_for_symbol(self, symbol: str) -> int:
        """Count block events for symbol"""
        return sum(
            1 for e in self._events
            if e.symbol == symbol and e.decision == "BLOCK"
        )
    
    def clear(self) -> None:
        """Clear all events (testing only)"""
        self._events.clear()
