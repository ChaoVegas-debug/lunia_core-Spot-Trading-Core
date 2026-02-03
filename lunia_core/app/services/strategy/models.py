"""
EPOCH E Phase E1: Strategy Models
StrategyContext (input) and IntentProposal (output)
"""
from __future__ import annotations

import enum
import time
from typing import Optional

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
    
    # FUTURE EXTENSION POINTS (not implemented in E1)
    # positions: Optional[Dict[str, Position]] = None
    # balances: Optional[Dict[str, Balance]] = None
    # sentiment: Optional[SentimentData] = None
    
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
