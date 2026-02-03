"""
PHASE 9.1 — PROTOCOL BOUNDARY HARDENING (CORE-SEALED)

Immutable boundary contract between sealed execution core and unsealed strategy sandbox.

ARCHITECTURE PRINCIPLES:
- Zero dependencies (stdlib only)
- No execution, no logic, no I/O
- Immutable data contracts
- Explicit versioning and type safety
- Fail-closed semantics

This layer defines what may be said, never what is done.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict

# ────────────────────────────────────────────────────────────────────────────────
# VERSIONING & IDENTITY
# ────────────────────────────────────────────────────────────────────────────────

PROTOCOL_VERSION = "1.0.1"  # Hard invariant: mismatch = REJECT
TimestampMs = int  # UTC epoch milliseconds


# ────────────────────────────────────────────────────────────────────────────────
# STRICT ENUMS (NO STRING DRIFT)
# ────────────────────────────────────────────────────────────────────────────────


class MarketRegime(Enum):
    """Market state classification."""
    TREND_UP = "trend_up"
    TREND_DOWN = "trend_down"
    CHOP = "chop"
    BREAKOUT = "breakout"
    COLLAPSE = "collapse"


class VolatilityState(Enum):
    """Volatility level classification."""
    CALM = "calm"
    NORMAL = "normal"
    ELEVATED = "elevated"
    EXTREME = "extreme"
    HALTED = "halted"


class TradeDirection(Enum):
    """Trade direction."""
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


class IntentType(Enum):
    """Strategy intent type."""
    ENTRY = "entry"
    EXIT = "exit"
    ADJUST = "adjust"
    NOOP = "noop"
    REJECT = "reject"  # Documentation of governance rejection only


class StrategyFrequency(Enum):
    """Strategy frequency classification."""
    HFT = "hft"
    SCALP = "scalp"
    INTRADAY = "intraday"
    SWING = "swing"
    POSITION = "position"


class RiskState(Enum):
    """Risk state classification."""
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    BLACK = "black"


# ────────────────────────────────────────────────────────────────────────────────
# READ-ONLY CONTEXT (CORE → STRATEGY)
# ────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MarketSnapshot:
    """Immutable market state snapshot provided to strategy."""
    symbol: str
    ts_ms: TimestampMs
    bid: float
    ask: float
    mid: float
    volume_24h: float
    volatility_state: VolatilityState
    market_regime: MarketRegime
    atr_14: float
    spread_pct: float


@dataclass(frozen=True)
class ShadowPosition:
    """Immutable position snapshot provided to strategy."""
    symbol: str
    direction: TradeDirection
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    entry_ts_ms: TimestampMs
    position_id: str


@dataclass(frozen=True)
class ShadowPortfolio:
    """Immutable portfolio snapshot provided to strategy."""
    base_currency: str
    equity: float
    available_balance: float
    margin_used: float
    margin_available: float
    positions: Dict[str, ShadowPosition]  # serialized with sorted keys
    daily_pnl: float
    total_pnl: float
    peak_equity: float
    drawdown_pct: float


@dataclass(frozen=True)
class GovernanceContext:
    """Immutable governance context provided to strategy."""
    ts_ms: TimestampMs
    run_id: str
    correlation_id: str

    is_live: bool
    is_reduce_only: bool
    allow_new_entries: bool

    max_position_size: float
    max_leverage: float

    risk_state: RiskState
    emergency_override_active: bool


# ────────────────────────────────────────────────────────────────────────────────
# STRATEGY OUTPUT (STRATEGY → CORE)
# ────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TradeExitPlan:
    """
    Exit plan for a trade.
    
    VALIDATION: At least one exit condition must be defined.
    """
    stop_loss_price: Optional[float]
    stop_loss_pct: Optional[float]
    take_profit_price: Optional[float]
    take_profit_pct: Optional[float]
    time_limit_ms: Optional[int]
    trail_start_pct: Optional[float]


@dataclass(frozen=True)
class StrategyIntent:
    """
    Strategy intent submitted to core for governance review.
    
    INVARIANTS:
    - ENTRY intents MUST include exit_plan
    - NOOP intents MUST include rationale
    - protocol_version MUST match PROTOCOL_VERSION
    - One intent per tick (MVP invariant)
    """
    intent_id: str
    ts_ms: TimestampMs
    protocol_version: str
    correlation_id: str

    intent_type: IntentType
    direction: Optional[TradeDirection]
    symbol: Optional[str]

    size_base: Optional[float]
    size_quote: Optional[float]

    exit_plan: Optional[TradeExitPlan]  # REQUIRED for ENTRY

    confidence: float
    rationale: str

    strategy_id: str
    strategy_frequency: StrategyFrequency

    is_hedge: bool = False
    is_scaling: bool = False


@dataclass
class StrategyManifest:
    """
    Strategy manifest declaring capabilities and constraints.
    
    Validated on load to ensure protocol version compatibility.
    """
    strategy_id: str
    name: str
    version: str
    protocol_version: str
    author: str
    frequency: StrategyFrequency

    supports_long: bool
    supports_short: bool
    requires_hedging: bool

    max_leverage: float
    preferred_timeframe: str

    is_valid: bool = field(init=False)

    def __post_init__(self):
        """Validate protocol version on initialization."""
        self.is_valid = self.protocol_version == PROTOCOL_VERSION
