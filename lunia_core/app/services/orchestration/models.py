"""
EPOCH E Phase E2.1: Approved Intent Model
The ONLY format ExecutionWorker accepts
"""
from __future__ import annotations

import time
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ApprovedIntent(BaseModel):
    """
    Approved intent - the ONLY input ExecutionWorker accepts
    
    LOCKED INVARIANTS:
    - Created ONLY from GovernanceDecision(APPROVE)
    - Immutable
    - Carries governance decision ID for audit trail
    - ExecutionWorker MUST reject anything not ApprovedIntent
    
    This is the contract between Governance and Execution.
    """
    
    # Intent identification
    intent_id: str = Field(..., description="Intent identifier (cross-reference)")
    strategy_id: str = Field(..., description="Strategy that generated this")
    symbol: str = Field(..., description="Trading pair")
    
    # Trading intent
    side: Literal["BUY", "SELL"] = Field(..., description="Order side")
    reference_price: Optional[float] = Field(None, description="Price at signal generation")
    
    # Governance approval (MANDATORY)
    governance_decision_id: str = Field(..., description="GovernanceDecision ID (audit trail)")
    approved_at_ms: int = Field(default_factory=lambda: int(time.time() * 1000), description="Approval timestamp")
    
    # Rationale (for audit)
    rationale: str = Field(..., description="Strategy rationale (propagated from intent)")
    
    class Config:
        frozen = True  # Immutable
