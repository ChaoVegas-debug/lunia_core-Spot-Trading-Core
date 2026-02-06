"""
EPOCH E Phase E1: Strategy Models
StrategyContext (input) and IntentProposal (output)
"""
from __future__ import annotations

import enum
import time
from typing import Optional, List

from pydantic import BaseModel, Field

from ..market_data.realtime.models import MarketSnapshot


class SignalSide(str, enum.Enum):
    """Signal side (direction)"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class StrategyContext(BaseModel):
    """
    Strategy input context (immutable snapshot of world state)
    
    This is the ONLY interface through which strategies receive data.
    
    Features:
    - Immutable (strategies cannot mutate)
    - Snapshot-based (deep copy from ThreadSafeSnapshotCache)
    - Future-proof (can extend with portfolio, balances, sentiment)
    
    LOCKED INVARIANTS:
    - MarketSnapshot is read-only (deep copy)
    - No await required
    - No blocking waits
    """
    
    # Symbol being evaluated
    symbol: str = Field(..., description="Trading pair (e.g., BTC/USDT)")
    
    # Current market snapshot (deep copy, immutable)
    snapshot: MarketSnapshot = Field(..., description="Current market snapshot (VALID)")
    
    # Snapshot metadata
    snapshot_version: int = Field(..., description="Snapshot version (monotonic)")
    received_at_ms: int = Field(default_factory=lambda: int(time.time() * 1000), description="Context creation timestamp (ms)")
    
    # Epoch 9.1: Market enrichment state (Phase 8.3 integration)
    market_state: Optional[dict] = Field(None, description="Deterministic market physics (volume, volatility, regime, liquidity)")
    # Structure:
    # {
    #   "volume": {"vol_1m": float, "vol_5m": float, ...},
    #   "volatility": {"atr": float, "vol_regime": str, ...},
    #   "regime": {"regime": str, "confidence": float},
    #   "liquidity": {"spread_pct": float, "imbalance": float, ...},
    #   "market_risk_flag": str,  # "SAFE" | "RISKY" | "DANGEROUS" | "UNKNOWN"
    #   "timestamp_ms": int
    # }
    
    # FUTURE EXTENSION POINTS (not implemented in E1)
    # positions: Optional[Dict[str, Position]] = None
    # balances: Optional[Dict[str, Balance]] = None
    # sentiment: Optional[SentimentData] = None
    
    # Epoch 9.1: Safe accessor methods (graceful degradation)
    
    def get_volatility_regime(self) -> str:
        """
        Get volatility regime with safe fallback.
        
        Returns:
            "UNKNOWN" | "LOW" | "MEDIUM" | "HIGH"
        """
        if not self.market_state:
            return "UNKNOWN"
        volatility = self.market_state.get("volatility", {})
        return volatility.get("vol_regime", "UNKNOWN") if isinstance(volatility, dict) else "UNKNOWN"
    
    def get_market_regime(self) -> str:
        """
        Get market regime with safe fallback.
        
        Returns:
            "UNKNOWN" | "RANGE" | "TREND" | "BREAKOUT"
        """
        if not self.market_state:
            return "UNKNOWN"
        regime = self.market_state.get("regime", {})
        return regime.get("regime", "UNKNOWN") if isinstance(regime, dict) else "UNKNOWN"
    
    def get_market_risk_flag(self) -> str:
        """
        Get overall market risk classification.
        
        Returns:
            "UNKNOWN" | "SAFE" | "RISKY" | "DANGEROUS"
        """
        if not self.market_state:
            return "UNKNOWN"
        return self.market_state.get("market_risk_flag", "UNKNOWN")
    
    def get_atr(self) -> Optional[float]:
        """
        Get ATR (Average True Range) if available.
        
        Returns:
            ATR value or None if not available
        """
        if not self.market_state:
            return None
        volatility = self.market_state.get("volatility", {})
        return volatility.get("atr") if isinstance(volatility, dict) else None
    
    def get_spread_pct(self) -> Optional[float]:
        """
        Get bid-ask spread percentage if available.
        
        Returns:
            Spread percentage or None if not available
        """
        if not self.market_state:
            return None
        liquidity = self.market_state.get("liquidity", {})
        return liquidity.get("spread_pct") if isinstance(liquidity, dict) else None
    
    def get_liquidity_stress(self) -> str:
        """
        Get liquidity stress classification.
        
        Returns:
            "UNKNOWN" | "NORMAL" | "WARNING" | "CRITICAL"
        """
        if not self.market_state:
            return "UNKNOWN"
        liquidity = self.market_state.get("liquidity", {})
        return liquidity.get("liquidity_stress", "UNKNOWN") if isinstance(liquidity, dict) else "UNKNOWN"
    
    class Config:
        arbitrary_types_allowed = True  # Allow MarketSnapshot


class IntentProposal(BaseModel):
    """
    Strategy output (passive proposal, NOT an order)
    
    This is the ONLY output strategies can produce.
    
    LOCKED INVARIANTS:
    - IntentProposal ≠ Order
    - No execution authority
    - No quantity enforcement
    - Passive (governance decides whether to act)
    - Explainable (rationale required)
    - Rejectable (governance has veto power)
    """
    
    # Strategy metadata
    strategy_id: str = Field(..., description="Strategy that generated this proposal")
    
    # Symbol and direction
    symbol: str = Field(..., description="Trading pair")
    side: SignalSide = Field(..., description="Signal direction (BUY/SELL/HOLD)")
    
    # Signal strength (normalized 0.0-1.0)
    signal_strength: float = Field(..., ge=0.0, le=1.0, description="Signal confidence (0.0=weak, 1.0=strong)")
    
    # Reference price (for audit/comparison)
    reference_price: Optional[float] = Field(None, description="Price at signal generation (mid/last)")
    
    # Audit trail
    rationale: str = Field(..., description="Human & machine-readable explanation")
    
    # Timestamps
    created_at_ms: int = Field(default_factory=lambda: int(time.time() * 1000), description="Proposal creation time")
    expires_at_ms: Optional[int] = Field(None, description="Proposal expiration (optional)")
    
    # Extension point for governance metadata
    governance_metadata: Optional[dict] = Field(None, description="Governance-specific context")
    
    class Config:
        use_enum_values = True

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Epoch 9.2: ExecutionProposal (Orchestrator Output)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class RejectionReasonCode(str, enum.Enum):
    """Standardized reason codes for strategy rejection"""
    BELOW_THRESHOLD = "BELOW_THRESHOLD"  # Signal strength too weak
    REGIME_FORBIDDEN = "REGIME_FORBIDDEN"  # Market regime not allowed by descriptor
    VOLATILITY_TOO_HIGH = "VOLATILITY_TOO_HIGH"  # Exceeds max volatility
    LIQUIDITY_STRESS = "LIQUIDITY_STRESS"  # Liquidity concerns
    CONFLICT_LOST = "CONFLICT_LOST"  # Lost in BUY vs SELL tie-break
    RISK_OFF_OVERRIDE = "RISK_OFF_OVERRIDE"  # Overridden by risk-off signal
    STRATEGY_ERROR = "STRATEGY_ERROR"  # Strategy raised exception
    TIME_BUDGET_EXCEEDED = "TIME_BUDGET_EXCEEDED"  # Soft timeout exceeded


class RejectedStrategy(BaseModel):
    """
    Record of strategy rejection with reason.
    
    Used in ExecutionProposal to provide full traceability.
    """
    strategy_id: str
    reason_code: RejectionReasonCode
    detail: str  # Human-readable explanation


class ExecutionProposal(BaseModel):
    """
    Epoch 9.2: Executive Function Output — The Verdict
    
    Single, deterministic trading proposal synthesized from multiple strategies.
    
    Invariants:
    - EXACTLY ONE proposal per tick
    - Immutable once created
    - Full traceability (accepted + rejected strategies)
    - Deterministic (same inputs → same output)
    
    Safety:
    - If NO_TRADE, explicit reasons provided
    - Risk-off overrides are explicit
    - Conflict resolution is documented
    """
    # Identity
    id: str = Field(default_factory=lambda: str(__import__('uuid').uuid4()), description="UUID4")
    timestamp_utc: str = Field(
        default_factory=lambda: __import__('datetime').datetime.utcnow().isoformat() + 'Z',
        description="ISO-8601 UTC timestamp"
    )
    
    # Trading decision
    symbol: str
    side: SignalSide  # BUY / SELL / HOLD
    aggregated_confidence: float = Field(..., ge=0.0, le=1.0, description="Final confidence (0.0-1.0)")
    
    # Traceability
    target_strategies: List[str] = Field(default_factory=list, description="Contributing strategy IDs")
    rejected_strategies: List[RejectedStrategy] = Field(default_factory=list, description="Rejected with reasons")
    
    # Governance audit trail
    orchestration_reasoning: str = Field(..., description="Human-readable orchestration logic")
    orchestration_reason_codes: List[str] = Field(default_factory=list, description="Machine-readable codes")
    
    # Market context snapshot
    market_state_snapshot: dict = Field(default_factory=dict, description="market_state used for decision")
    
    # Optional reference price (from winning strategy)
    reference_price: Optional[float] = None
    
    class Config:
        frozen = True  # Immutable
        use_enum_values = True
