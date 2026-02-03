"""
EPOCH E Phase E3.1: Risk Context Provider Base Interfaces
Canonical contracts for deterministic, fail-closed data provision
"""
from __future__ import annotations

from typing import Dict, List, Optional, Any, Protocol
from pydantic import BaseModel, Field

from app.services.risk.models import RiskContext
from app.services.strategy.models import IntentProposal
from app.services.market_data.realtime.models import MarketSnapshot
from app.services.governance.context import GovernanceContext


class RiskContextBuildResult(BaseModel):
    """
    Result from building RiskContext
    
    CRITICAL SEMANTICS:
    - ok = True: context is COMPLETE and VALID for risk assessment
    - ok = False: context is INVALID/INCOMPLETE, MUST NOT be used
    
    NO PARTIAL CONTEXT:
    - If ANY required component fails, ok = False
    - Partial contexts (e.g., "Equity OK but Vol Missing") are FORBIDDEN
    - Context is either COMPLETE or ABSENT
    """
    
    ok: bool = Field(..., description="True if context is COMPLETE and VALID")
    context: Optional[RiskContext] = Field(None, description="Complete RiskContext (only if ok=True)")
    
    # Error classification (STRICT)
    blocking_errors: List[str] = Field(default_factory=list, description="Errors that BLOCK execution")
    warnings: List[str] = Field(default_factory=list, description="Informational warnings")
    
    # Audit metadata (MANDATORY)
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Provenance and audit trail")
    
    class Config:
        frozen = True  # Immutable


class IRiskContextProvider(Protocol):
    """
    Provider interface for building RiskContext
    
    LOCKED INVARIANTS:
    - ONE INTENT → ONE CONTEXT (context built for exactly one intent)
    - IDEMPOTENT (same inputs + now_ms → bit-identical output)
    - SIDE-EFFECT FREE (read-only, no mutations)
    - COMPLETE OR NOTHING (no partial contexts)
    - SYMBOL UNIVERSE (intent.symbol defines minimum required symbols)
    """
    
    def build_context(
        self,
        intent: IntentProposal,
        snapshot: MarketSnapshot,
        gov_context: GovernanceContext,
        now_ms: Optional[int] = None
    ) -> RiskContextBuildResult:
        """
        Build RiskContext for ONE intent
        
        Args:
            intent: IntentProposal (defines symbol universe)
            snapshot: MarketSnapshot (source of mark prices)
            gov_context: GovernanceContext
            now_ms: Optional timestamp for deterministic tests
        
        Returns:
            RiskContextBuildResult with ok=True (complete) or ok=False (failed)
        """
        ...


# Standard provider error codes (machine-readable)
class ProviderErrorCodes:
    """Standard error codes for provider failures"""
    
    # Portfolio errors
    EQUITY_MISSING = "RISKCTX_EQUITY_MISSING"
    EQUITY_INVALID = "RISKCTX_EQUITY_INVALID"
    PEAK_EQUITY_INVALID = "RISKCTX_PEAK_EQUITY_INVALID"
    POSITIONS_MISSING = "RISKCTX_POSITIONS_MISSING"
    
    # Mark price errors
    MARKS_SNAPSHOT_INVALID = "RISKCTX_MARKS_SNAPSHOT_INVALID"
    MARKS_STALE = "RISKCTX_MARKS_STALE"
    MARKS_MISSING_PRICE = "RISKCTX_MARKS_MISSING_PRICE"
    
    # Volatility errors
    VOL_MISSING = "RISKCTX_VOL_MISSING"
    VOL_INSUFFICIENT_SAMPLES = "RISKCTX_VOL_INSUFFICIENT_SAMPLES"
    VOL_UNSUPPORTED_SOURCE = "RISKCTX_VOL_UNSUPPORTED_SOURCE"
    
    # System errors
    PROVIDER_EXCEPTION = "RISKCTX_PROVIDER_EXCEPTION"
    
    # Governance-facing error (aggregated)
    GOV_RISK_CONTEXT_UNAVAILABLE = "GOV_RISK_CONTEXT_UNAVAILABLE"
