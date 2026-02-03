"""
EPOCH E Phase E2: Governance Models
GovernanceDecision and related types
"""
from __future__ import annotations

import enum
import time
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field


class DecisionType(str, enum.Enum):
    """Governance decision type"""
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class GovernanceDecision(BaseModel):
    """
    Governance decision on an IntentProposal
    
    LOCKED INVARIANTS:
    - Every decision MUST have reason_codes (audit trail)
    - Metadata MUST be bounded and sanitized
    - Timestamp MUST be present
    - Decision MUST be APPROVE or REJECT (no MAYBE)
    
    This is the ONLY output from GovernanceEngine.
    """
    
    # Intent identification
    intent_id: str = Field(..., description="IntentProposal identifier (for cross-reference)")
    strategy_id: str = Field(..., description="Strategy that generated the intent")
    symbol: str = Field(..., description="Trading pair")
    
    # Decision
    decision: DecisionType = Field(..., description="APPROVE or REJECT")
    
    # Audit trail (MANDATORY)
    reason_codes: List[str] = Field(..., description="Machine-readable reason codes")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context (bounded)")
    
    # Timestamp
    decided_at_ms: int = Field(default_factory=lambda: int(time.time() * 1000), description="Decision timestamp")
    
    class Config:
        use_enum_values = True
