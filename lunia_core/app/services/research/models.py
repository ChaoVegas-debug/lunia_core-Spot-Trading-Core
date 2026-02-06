"""
Epoch D.1 — Research Data Contracts

FROZEN MODELS (Anti-Hallucination + Schema Enforcement)
"""
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator


# ============================================================================
# ENUMS
# ============================================================================

class MacroRegime(str, Enum):
    """Macro market regime classification."""
    RISK_ON = "RISK_ON"
    RISK_OFF = "RISK_OFF"
    NEUTRAL = "NEUTRAL"
    UNCERTAIN = "UNCERTAIN"


class VolatilityOutlook(str, Enum):
    """Expected volatility trajectory."""
    EXPANDING = "EXPANDING"
    COMPRESSING = "COMPRESSING"
    STABLE = "STABLE"


class RiskFlag(str, Enum):
    """Risk event flags (deterministic triggers)."""
    FOMC_TODAY = "FOMC_TODAY"
    CPI_SOON = "CPI_SOON"
    GEOPOLITICAL_RISK = "GEOPOLITICAL_RISK"
    WAR = "WAR"
    EXCHANGE_OUTAGE = "EXCHANGE_OUTAGE"
    LIQUIDITY_STRESS = "LIQUIDITY_STRESS"
    POLICY_SHOCK = "POLICY_SHOCK"
    LLM_ERROR = "LLM_ERROR"
    DATA_STALE = "DATA_STALE"
    SCHEMA_VIOLATION = "SCHEMA_VIOLATION"


# ============================================================================
# ANTI-HALLUCINATION CORE
# ============================================================================

class Evidence(BaseModel):
    """
    Evidence record (source of truth for claims).
    
    IMMUTABLE: All evidence is frozen after creation.
    """
    source_id: str
    source_type: Literal["NEWS", "CALENDAR", "MARKET"]
    title: str
    reference: str  # URL or deterministic ID
    published_at: datetime
    snippet: str = Field(..., max_length=500)
    reliability_tier: Literal["TIER_1", "TIER_2", "UNKNOWN"]
    
    class Config:
        frozen = True


class Claim(BaseModel):
    """
    Claim extracted from context.
    
    REQUIREMENT: Must cite evidence (empty evidence_ids = invalid).
    """
    claim_id: str
    text: str
    evidence_ids: list[str]
    
    @validator('evidence_ids')
    def must_have_evidence(cls, v):
        """Claims without evidence are hallucinations."""
        if not v:
            raise ValueError("Claims must cite evidence (anti-hallucination)")
        return v
    
    class Config:
        frozen = True


# ============================================================================
# STAGE 1: EXTRACT PAYLOAD (FACTS ONLY)
# ============================================================================

class ExtractPayload(BaseModel):
    """
    Stage 1 output contract.
    
    FORBIDDEN: regime, sentiment, confidence, volatility.
    Stage 1 is FACTS ONLY. Any regime/sentiment output = contract violation.
    """
    evidence: list[Evidence]
    claims: list[Claim]
    extracted_at: datetime
    extract_prompt_hash: str
    context_hash: str
    
    @validator('evidence')
    def validate_evidence(cls, v):
        """Evidence must be non-empty for valid extract."""
        if not v:
            raise ValueError("ExtractPayload requires evidence")
        return v
    
    class Config:
        frozen = True
        extra = 'forbid'  # Reject unknown fields


# ============================================================================
# STAGE 2: JUDGE PAYLOAD
# ============================================================================

class JudgePayload(BaseModel):
    """
    Stage 2 output contract (regime + sentiment analysis).
    
    RANGES ENFORCED:
    - sentiment_score: [-1, 1]
    - confidence: [0, 1]
    """
    regime: MacroRegime
    volatility_outlook: VolatilityOutlook
    sentiment_score: float
    risk_flags: list[RiskFlag]
    confidence: float
    reasoning: str
    judge_prompt_hash: str
    context_hash: str
    
    @validator('sentiment_score')
    def valid_sentiment(cls, v):
        if not -1.0 <= v <= 1.0:
            raise ValueError(f"Sentiment must be in [-1, 1], got {v}")
        return v
    
    @validator('confidence')
    def valid_confidence(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Confidence must be in [0, 1], got {v}")
        return v
    
    class Config:
        frozen = True


# ============================================================================
# FINAL PUBLISHED CONTRACT
# ============================================================================

class ResearchReport(BaseModel):
    """
    Final research report (published to consumers).
    
    VALIDATION:
    - Claims must reference existing evidence
    - valid_until must be bounded
    - Staleness detection built-in
    """
    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime
    valid_until: datetime
    regime: MacroRegime
    volatility_outlook: VolatilityOutlook
    sentiment_score: float
    risk_flags: list[RiskFlag]
    claims: list[Claim]
    evidence: list[Evidence]
    reasoning: str
    confidence: float
    prompt_hash: str
    context_hash: str
    provider_snapshot: dict[str, Any]
    
    def is_stale(self, now_utc: datetime) -> bool:
        """Check if report has expired."""
        return now_utc > self.valid_until
    
    @validator('claims')
    def claims_must_reference_evidence(cls, claims, values):
        """Enforce evidence-claim binding."""
        evidence_ids = {e.source_id for e in values.get('evidence', [])}
        for claim in claims:
            for eid in claim.evidence_ids:
                if eid not in evidence_ids:
                    raise ValueError(
                        f"Claim {claim.claim_id} references "
                        f"non-existent evidence {eid}"
                    )
        return claims
    
    @validator('valid_until')
    def valid_until_bounded(cls, v, values):
        """Prevent unbounded TTL."""
        timestamp = values.get('timestamp')
        if timestamp:
            delta = (v - timestamp).total_seconds()
            if delta < 0:
                raise ValueError("valid_until must be after timestamp")
            if delta > 3600:  # Max 1 hour TTL
                raise ValueError("valid_until exceeds 1 hour max TTL")
        return v
    
    class Config:
        frozen = True


def create_default_uncertain_report(now_utc: datetime) -> ResearchReport:
    """
    Create fail-safe UNCERTAIN report (used when data missing/stale).
    
    Returns:
        ResearchReport with UNCERTAIN regime, 0.0 confidence, DATA_STALE flag
    """
    return ResearchReport(
        timestamp=now_utc,
        valid_until=now_utc.replace(microsecond=0) + timedelta(minutes=5),
        regime=MacroRegime.UNCERTAIN,
        volatility_outlook=VolatilityOutlook.STABLE,
        sentiment_score=0.0,
        risk_flags=[RiskFlag.DATA_STALE],
        claims=[],
        evidence=[],
        reasoning="No valid research data available (fail-safe mode)",
        confidence=0.0,
        prompt_hash="",
        context_hash="",
        provider_snapshot={}
    )
