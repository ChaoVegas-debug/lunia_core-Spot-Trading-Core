"""
EPOCH B: Pydantic Schemas for Proposal Domain
API request/response models
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ENUM LITERALS (matching models.py)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ProposalStatusType = str  # DRAFT, PENDING_USER, APPROVED, etc.
ProposalActionType = str  # BUY, SELL, HEDGE, REBALANCE
RiskLabelType = str  # LOW_RISK, MEDIUM_RISK, HIGH_RISK, EXTREME_RISK
HorizonType = str  # INTRADAY, SWING, POSITION, LONG_TERM
DataFreshnessStateType = str  # FRESH, STALE, DEGRADED, OFFLINE
ProposalAuditEventTypeType = str  # PROPOSAL_CREATED, etc.


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# NESTED SCHEMAS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class GovernanceSnapshot(BaseModel):
    """Governance state captured at proposal creation"""
    global_stop: bool
    system_mode: str
    run_mode: str
    airlock_status: str
    live_allowed: bool
    tier: Optional[str] = None
    data_freshness_state: DataFreshnessStateType
    data_freshness_metrics: Dict[str, Any]
    timestamp: str  # ISO8601


class ThesisDNAGene(BaseModel):
    """Individual gene in thesis DNA chromosome"""
    key: str
    confidence: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0, le=1.0)
    evidence_refs: List[str] = Field(default_factory=list)
    validation_window: Optional[int] = None  # seconds
    mutation_resistance: float = Field(default=0.5, ge=0.0, le=1.0)


class ThesisDNA(BaseModel):
    """Structured evidence graph - chromosomes/genes"""
    chromosomes: Dict[str, List[ThesisDNAGene]] = Field(
        description="technical, fundamental, sentiment, flow, macro"
    )
    
    # BLOCKER B FIX: Pydantic v1 syntax (validator instead of field_validator)
    @validator("chromosomes")
    def validate_chromosomes(cls, v):
        """Validate chromosome structure"""
        required_chromosomes = {"technical", "fundamental", "sentiment", "flow", "macro"}
        if not required_chromosomes.issubset(set(v.keys())):
            raise ValueError(f"Missing chromosomes. Required: {required_chromosomes}")
        
        # Validate each chromosome's gene weights sum to ~1.0
        for chrom_name, genes in v.items():
            if genes:
                total_weight = sum(g.weight for g in genes)
                if not (0.99 <= total_weight <= 1.01):
                    raise ValueError(f"Chromosome {chrom_name} gene weights sum to {total_weight}, must be ~1.0")
        
        return v


class FactorAttribution(BaseModel):
    """Factor contribution to thesis"""
    factor: str
    weight: int = Field(ge=0, le=100)
    confidence: int = Field(ge=0, le=100)


class ExecutionPlanPreview(BaseModel):
    """Non-executable plan preview"""
    entry_zone_low: Optional[float] = None
    entry_zone_high: Optional[float] = None
    take_profit_targets: List[float] = Field(default_factory=list)
    stop_loss: Optional[float] = None
    max_slippage_percent: Optional[float] = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# REQUEST SCHEMAS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ProposalCreate(BaseModel):
    """Create new proposal"""
    asset: str
    action: ProposalActionType
    horizon: HorizonType
    risk_label: RiskLabelType
    priority_score: int = Field(default=50, ge=0, le=100)
    
    thesis_summary: str = Field(min_length=10)
    thesis_dna: ThesisDNA
    invalidation_rules: Optional[Dict[str, Any]] = None
    
    factor_attribution: List[FactorAttribution]
    model_votes: Optional[List[Dict[str, Any]]] = None
    confidence_score: float = Field(ge=0.0, le=1.0)
    devils_advocate: str = Field(min_length=10, description="MANDATORY counter-case")
    
    execution_plan_preview: Optional[ExecutionPlanPreview] = None
    expires_at: Optional[str] = None  # ISO8601
    
    # BLOCKER B FIX: Pydantic v1 syntax
    @validator("factor_attribution")
    def validate_factor_weights(cls, v):
        """Factor weights must sum to 100"""
        total = sum(f.weight for f in v)
        if not (99 <= total <= 101):
            raise ValueError(f"Factor attribution weights sum to {total}, must equal 100")
        return v


class ApprovalRequest(BaseModel):
    """Approve proposal"""
    notes: Optional[str] = None
    size_adjustment: float = Field(default=1.0, ge=0.1, le=1.0, description="% of proposed size")


class RejectionRequest(BaseModel):
    """Reject proposal"""
    reason: str = Field(min_length=1, description="MANDATORY rejection reason")
    comment: Optional[str] = None


class RequestChangesRequest(BaseModel):
    """Request changes to proposal"""
    requested_changes: str = Field(min_length=10)
    comment: Optional[str] = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RESPONSE SCHEMAS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ProposalResponse(BaseModel):
    """Full proposal detail"""
    id: str
    version: int
    status: ProposalStatusType
    
    # Classification
    asset: str
    action: ProposalActionType
    horizon: HorizonType
    risk_label: RiskLabelType
    priority_score: int
    
    # Governance
    governance_snapshot: Dict[str, Any]
    
    # Thesis
    thesis_summary: str
    thesis_dna: Dict[str, Any]
    invalidation_rules: Optional[Dict[str, Any]]
    
    # Evidence
    factor_attribution: List[Dict[str, Any]]
    model_votes: Optional[List[Dict[str, Any]]]
    confidence_score: float
    devils_advocate: str
    
    # Execution plan
    execution_plan_preview: Optional[Dict[str, Any]]
    
    # Lifecycle
    created_at: str
    updated_at: str
    expires_at: Optional[str]
    supersedes_id: Optional[str]
    
    # Actors
    created_by_user_id: Optional[int]
    approved_by_user_id: Optional[int]
    rejected_by_user_id: Optional[int]
    
    # Event timestamps
    approved_at: Optional[str]
    rejected_at: Optional[str]
    rejection_reason: Optional[str]
    
    class Config:
        from_attributes = True


class ProposalListItem(BaseModel):
    """Proposal list item (summary)"""
    id: str
    version: int
    status: ProposalStatusType
    asset: str
    action: ProposalActionType
    risk_label: RiskLabelType
    priority_score: int
    confidence_score: float
    thesis_summary: str
    created_at: str
    expires_at: Optional[str]
    
    class Config:
        from_attributes = True


class ProposalListResponse(BaseModel):
    """Paginated proposal list"""
    proposals: List[ProposalListItem]
    total: int
    page: int
    page_size: int


class ExecutionIntentResponse(BaseModel):
    """Execution intent detail"""
    id: str
    proposal_id: str
    status: str
    plan_snapshot: Dict[str, Any]
    governance_snapshot_at_approval: Dict[str, Any]
    created_at: str
    created_by_user_id: int
    
    class Config:
        from_attributes = True


class ProposalAuditEventResponse(BaseModel):
    """Audit event detail"""
    id: str
    proposal_id: str
    event_type: ProposalAuditEventTypeType
    actor_user_id: Optional[int]
    actor_role: Optional[str]
    timestamp: str
    governance_snapshot: Dict[str, Any]
    confidence_score_at_decision: Optional[float]
    data_freshness_state_at_decision: Optional[DataFreshnessStateType]
    event_metadata: Optional[Dict[str, Any]]
    
    class Config:
        from_attributes = True


class AuditTrailResponse(BaseModel):
    """Full audit trail for proposal"""
    proposal_id: str
    events: List[ProposalAuditEventResponse]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GHOST ENGINE SCHEMAS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class GhostTestRequest(BaseModel):
    """Ghost test simulation request"""
    proposal_id: str
    size_scenarios: List[float] = Field(default=[0.1, 0.5, 1.0], description="% of proposed size")


class GhostResult(BaseModel):
    """Ghost test simulation result (deterministic)"""
    scenario_size: float  # % of proposed size
    estimated_roi: float  # %
    estimated_drawdown: float  # %
    estimated_win_rate: float  # 0.0 - 1.0
    confidence_impact: float  # adjustment to confidence score
    slippage_estimate: float  # %
    market_impact_estimate: float  # %
    
    # Warnings
    warnings: List[str] = Field(default_factory=list)


class GhostTestResponse(BaseModel):
    """Ghost test response"""
    proposal_id: str
    results: List[GhostResult]
    deterministic: bool = Field(default=True, description="EPOCH B: always deterministic")
    timestamp: str
