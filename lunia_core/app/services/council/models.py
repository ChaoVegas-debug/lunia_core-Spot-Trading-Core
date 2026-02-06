"""
Epoch 10: Adversarial Council — Models

Immutable models for governance verdicts & veto reasons.
"""
import enum
from typing import List, Dict, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class CouncilDecision(str, enum.Enum):
    """Council's final decision on a proposal"""
    APPROVE = "APPROVE"                # Proposal passes
    VETO = "VETO"                      # Proposal blocked
    DOWNGRADE_TO_HOLD = "DOWNGRADE_TO_HOLD"  # Force to HOLD


class VetoReasonCode(str, enum.Enum):
    """Standardized veto/warning reason codes"""
    DANGEROUS_MARKET = "DANGEROUS_MARKET"          # market_risk_flag == "DANGEROUS"
    VOLATILITY_SPIKE = "VOLATILITY_SPIKE"          # Extreme volatility detected
    LIQUIDITY_CRISIS = "LIQUIDITY_CRISIS"          # liquidity_stress == "CRITICAL"
    AI_RISK_FLAG = "AI_RISK_FLAG"                  # AI flagged HIGH_RISK
    METRICS_DEGRADATION = "METRICS_DEGRADATION"    # Strategy metrics poor
    COOLDOWN_ACTIVE = "COOLDOWN_ACTIVE"            # Post-trade cooldown
    UNKNOWN = "UNKNOWN"                            # Unclassified


class CouncilVerdict(BaseModel):
    """
    Immutable verdict from Adversarial Council.
    
    This wraps an ExecutionProposal with governance decision.
    """
    # Identity
    id: str = Field(default_factory=lambda: str(__import__('uuid').uuid4()))
    proposal_id: str = Field(..., description="ExecutionProposal ID reviewed")
    
    # Decision
    decision: CouncilDecision = Field(..., description="APPROVE/VETO/DOWNGRADE")
    veto_reason_codes: List[str] = Field(
        default_factory=list,
        description="Machine-readable veto reasons"
    )
    reasoning: str = Field(
        ...,
        description="Human-readable summary of decision"
    )
    
    # Traceability (Full Audit Log)
    votes: List[Dict[str, str]] = Field(
        default_factory=list,
        description="[{member_id, vote, reason, severity}] - includes dissenting opinions"
    )
    
    # Market Context Snapshot (Proof of State)
    market_state_snapshot: Dict = Field(
        default_factory=dict,
        description="Market state at time of review"
    )
    
    # Temporal
    created_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + 'Z',
        description="ISO-8601 timestamp"
    )
    
    class Config:
        frozen = True  # Immutable
        use_enum_values = True


class CouncilFinding(BaseModel):
    """
    Individual member's finding.
    
    Used internally by Council members to report their assessment.
    """
    member_id: str
    severity: str  # "INFO" | "WARN" | "VETO"
    reason_code: str  # VetoReasonCode value
    message: str  #Human-readable detail
