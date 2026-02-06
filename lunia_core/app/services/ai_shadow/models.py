"""
Epoch 9.3: AI Shadow Observer — Models

This module defines the data models for AI shadow observations of ExecutionProposals.

The AI Shadow is a NON-BLOCKING commentary system that:
- Observes final ExecutionProposals asynchronously
- Provides agreement/disagreement analysis
- Offers risk assessment from AI perspective
- Suggests alternatives (advisory only)

HARD INVARIANT: AI has ZERO execution authority. It observes and comments ONLY.
"""
import enum
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class AIRiskAssessment(str, enum.Enum):
    """AI's risk assessment of the proposal"""
    SAFE = "SAFE"              # AI agrees, low risk
    CAUTION = "CAUTION"        # AI has concerns
    HIGH_RISK = "HIGH_RISK"    # AI strongly disagrees


class AIShadowReport(BaseModel):
    """
    AI Shadow's commentary on an ExecutionProposal.
    
    This is ADVISORY ONLY — AI cannot override the core decision.
    
    Lifecycle:
    1. Orchestrator produces ExecutionProposal (sync, deterministic)
    2. Observer dispatches async AI analysis (fire-and-forget)
    3. AI returns commentary (eventually)
    4. Report persisted for human review
    
    Fields:
    - proposal_id: Links to ExecutionProposal (1:1)
    - ai_agrees: Does AI agree with the core decision?
    - ai_risk_assessment: AI's risk level assessment
    - ai_commentary: Human-readable explanation
    - alternative_suggestion: What AI would have done instead (if disagrees)
    - confidence_score: AI's confidence in its own assessment (0.0-1.0)
    - analysis_duration_ms: How long AI took to analyze
    - created_at: When report was generated
    """
    # Identity & Linkage
    id: str = Field(default_factory=lambda: str(__import__('uuid').uuid4()))
    proposal_id: str = Field(..., description="ExecutionProposal ID this report analyzes")
    
    # AI Assessment
    ai_agrees: bool = Field(..., description="Does AI agree with core decision?")
    ai_risk_assessment: AIRiskAssessment = Field(..., description="AI's risk assessment")
    ai_commentary: str = Field(..., description="AI's explanation of its assessment")
    alternative_suggestion: Optional[str] = Field(
        None,
        description="What AI would recommend instead (if disagrees)"
    )
    
    # Metadata
    confidence_score: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="AI's confidence in its own assessment"
    )
    analysis_duration_ms: Optional[int] = Field(
        None,
        description="Time AI took to analyze (ms)"
    )
    created_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + 'Z',
        description="ISO-8601 UTC timestamp"
    )
    
    class Config:
        use_enum_values = True


# Database model placeholder (if persistence needed)
# For now, AIShadowReport can be stored as JSON or in a dedicated table
# Future: Create SQLAlchemy model with FK to execution_proposals table
