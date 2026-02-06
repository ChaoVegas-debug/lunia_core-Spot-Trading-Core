"""
Risk Governor Models — Immutable Portfolio State and Decisions

All models use frozen=True for immutability and determinism.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# =============================================================================
# PORTFOLIO STATE
# =============================================================================

class Position(BaseModel):
    """
    Individual position in portfolio.
    
    Represents a single asset holding with mark-to-market valuation.
    """
    symbol: str
    side: str  # "LONG" | "SHORT"
    quantity: float
    avg_entry_price: float
    mark_price: float
    notional: float  # quantity * mark_price (signed)
    
    class Config:
        frozen = True
        use_enum_values = True


class PendingOrderExposure(BaseModel):
    """
    In-flight order exposure for pessimistic accounting.
    
    Represents orders submitted but not yet filled/cancelled.
    Used to prevent double-counting in exposure calculations.
    """
    symbol: str
    cluster_id: str
    notional: float  # Signed notional (+ for buy, - for sell in some contexts)
    created_at_ms: int
    
    class Config:
        frozen = True


class PortfolioSnapshot(BaseModel):
    """
    Immutable portfolio state snapshot at specific timestamp.
    
    Canonical source for all portfolio-level calculations.
    Must include prices for all positions and target symbols.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    as_of_ms: int  # Snapshot timestamp (for staleness checks)
    
    # Base currency
    quote_ccy: str = "USDT"
    
    # Capital
    total_equity: float  # Total portfolio value in quote_ccy
    cash_available: Optional[float] = None  # Available buying power
    
    # Holdings
    positions: List[Position] = Field(default_factory=list)
    
    # Prices (symbol -> quote_ccy price)
    prices: Dict[str, float] = Field(default_factory=dict)
    
    # Pending orders (for pessimistic accounting)
    pending: List[PendingOrderExposure] = Field(default_factory=list)
    
    # Extensibility
    metadata: Dict = Field(default_factory=dict)
    
    class Config:
        frozen = True


# =============================================================================
# DECISION TYPES
# =============================================================================

class Decision(str, Enum):
    """Governor decision outcomes"""
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    DOWNGRADE_TO_DRY_RUN = "DOWNGRADE_TO_DRY_RUN"
    REQUIRES_MANUAL_REVIEW = "REQUIRES_MANUAL_REVIEW"
    LOG_ONLY = "LOG_ONLY"


class ReasonCode(str, Enum):
    """Standardized reason codes for decisions"""
    
    # Missing data (BLOCK)
    MISSING_PORTFOLIO_SNAPSHOT = "MISSING_PORTFOLIO_SNAPSHOT"
    MISSING_PRICE = "MISSING_PRICE"
    DATA_STALE = "DATA_STALE"
    
    # Hard limit violations (BLOCK)
    ORDER_NOTIONAL_TOO_LARGE = "ORDER_NOTIONAL_TOO_LARGE"
    SYMBOL_POSITION_CAP_EXCEEDED = "SYMBOL_POSITION_CAP_EXCEEDED"
    GROSS_EXPOSURE_CAP_EXCEEDED = "GROSS_EXPOSURE_CAP_EXCEEDED"
    NET_EXPOSURE_CAP_EXCEEDED = "NET_EXPOSURE_CAP_EXCEEDED"
    CLUSTER_EXPOSURE_CAP_EXCEEDED = "CLUSTER_EXPOSURE_CAP_EXCEEDED"
    ORDER_RATE_LOOP = "ORDER_RATE_LOOP"
    CIRCUIT_BREAKER_TRIPPED = "CIRCUIT_BREAKER_TRIPPED"
    
    # Soft warnings (MANUAL_REVIEW or DOWNGRADE)
    SOFT_WARN_SYMBOL_CONCENTRATION = "SOFT_WARN_SYMBOL_CONCENTRATION"
    SOFT_WARN_GROSS_EXPOSURE = "SOFT_WARN_GROSS_EXPOSURE"
    SOFT_WARN_CLUSTER_EXPOSURE = "SOFT_WARN_CLUSTER_EXPOSURE"
    
    # Internal errors (fail-closed)
    INTERNAL_ERROR_FAIL_CLOSED = "INTERNAL_ERROR_FAIL_CLOSED"


class GovernorDecision(BaseModel):
    """
    Immutable risk governance decision.
    
    Records the governor's evaluation of an order plan against portfolio limits.
    All decisions are journaled for audit trail.
    """
    verdict_id: str
    plan_id: str
    
    # Core decision
    decision: Decision
    reason_codes: List[ReasonCode]
    reasoning: str  # Human-readable explanation
    
    # Audit trail
    audit: Dict  # Computed metrics, intermediate values
    limits_snapshot: Dict  # Limits in effect at decision time
    correlation_cluster_id: str
    
    # Circuit breaker context
    window_count_orders_hour: Optional[int] = None
    consecutive_blocks: Optional[int] = None
    halt_recommended: bool = False
    
    class Config:
        frozen = True
        use_enum_values = True
