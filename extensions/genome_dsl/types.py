"""
PHASE 11 — GENOME DSL: Type System (AST Nodes)

The Language Constitution - all allowed DSL nodes as frozen dataclasses.

CRITICAL RULES:
- DSL is DATA, not code (no eval/exec)
- All nodes frozen (immutable)
- Strict typing (FLOAT | BOOL | STRING | SIGNAL)
- Whitelist only (no dynamic node creation)
"""

from dataclasses import dataclass
from typing import Any, List, Optional, Dict, Union


# ────────────────────────────────────────────────────────────────────────────────
# TYPE CONSTANTS
# ────────────────────────────────────────────────────────────────────────────────

FLOAT = "FLOAT"
BOOL = "BOOL"
STRING = "STRING"
SIGNAL = "SIGNAL"


# ────────────────────────────────────────────────────────────────────────────────
# CATEGORY 1: LITERALS
# ────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ConstFloat:
    """Constant float literal."""
    value: float
    return_type: str = FLOAT


@dataclass(frozen=True)
class ConstInt:
    """Constant integer literal (auto-cast to float for arithmetic)."""
    value: int
    return_type: str = FLOAT


@dataclass(frozen=True)
class ConstBool:
    """Constant boolean literal."""
    value: bool
    return_type: str = BOOL


@dataclass(frozen=True)
class ConstString:
    """Constant string literal (labels only, not logic)."""
    value: str
    return_type: str = STRING


# ────────────────────────────────────────────────────────────────────────────────
# CATEGORY 2: MARKET DATA (READ-ONLY from MarketSnapshot)
# ────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PriceMid:
    """Current mid price from market snapshot."""
    return_type: str = FLOAT


@dataclass(frozen=True)
class PriceBid:
    """Current bid price from market snapshot."""
    return_type: str = FLOAT


@dataclass(frozen=True)
class PriceAsk:
    """Current ask price from market snapshot."""
    return_type: str = FLOAT


@dataclass(frozen=True)
class SpreadPct:
    """Current spread percentage from market snapshot."""
    return_type: str = FLOAT


@dataclass(frozen=True)
class Volume:
    """24h volume from market snapshot."""
    return_type: str = FLOAT


@dataclass(frozen=True)
class VolatilityState:
    """Current volatility state enum value from market snapshot."""
    return_type: str = STRING


# ────────────────────────────────────────────────────────────────────────────────
# CATEGORY 3: INDICATORS (Deterministic, NO HISTORY ACCESS)
# ────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SMA:
    """Simple Moving Average (simulated from snapshot data)."""
    window: int
    source: Any  # Node[FLOAT]
    return_type: str = FLOAT


@dataclass(frozen=True)
class EMA:
    """Exponential Moving Average (simulated from snapshot data)."""
    window: int
    source: Any  # Node[FLOAT]
    return_type: str = FLOAT


@dataclass(frozen=True)
class RSI:
    """Relative Strength Index (simulated from snapshot data)."""
    window: int
    source: Any  # Node[FLOAT]
    return_type: str = FLOAT


@dataclass(frozen=True)
class ATR:
    """Average True Range (must exist in snapshot, e.g., atr_14)."""
    window: int  # Must match snapshot field
    return_type: str = FLOAT


@dataclass(frozen=True)
class Highest:
    """Highest value over window (simulated)."""
    window: int
    source: Any  # Node[FLOAT]
    return_type: str = FLOAT


@dataclass(frozen=True)
class Lowest:
    """Lowest value over window (simulated)."""
    window: int
    source: Any  # Node[FLOAT]
    return_type: str = FLOAT


@dataclass(frozen=True)
class ROC:
    """Rate of Change (simulated)."""
    window: int
    source: Any  # Node[FLOAT]
    return_type: str = FLOAT


# ────────────────────────────────────────────────────────────────────────────────
# CATEGORY 4: COMPARATORS (return BOOL)
# ────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GreaterThan:
    """left > right"""
    left: Any  # Node[FLOAT]
    right: Any  # Node[FLOAT]
    return_type: str = BOOL


@dataclass(frozen=True)
class LessThan:
    """left < right"""
    left: Any  # Node[FLOAT]
    right: Any  # Node[FLOAT]
    return_type: str = BOOL


@dataclass(frozen=True)
class Equal:
    """left == right"""
    left: Any
    right: Any
    return_type: str = BOOL


@dataclass(frozen=True)
class CrossAbove:
    """left crosses above right (current > right, previous <= right)."""
    left: Any  # Node[FLOAT]
    right: Any  # Node[FLOAT]
    return_type: str = BOOL


@dataclass(frozen=True)
class CrossBelow:
    """left crosses below right (current < right, previous >= right)."""
    left: Any  # Node[FLOAT]
    right: Any  # Node[FLOAT]
    return_type: str = BOOL


# ────────────────────────────────────────────────────────────────────────────────
# CATEGORY 5: BOOLEAN LOGIC
# ────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class And:
    """Logical AND of multiple boolean nodes (max 5 children)."""
    nodes: List[Any]  # List[Node[BOOL]], max 5
    return_type: str = BOOL


@dataclass(frozen=True)
class Or:
    """Logical OR of multiple boolean nodes (max 5 children)."""
    nodes: List[Any]  # List[Node[BOOL]], max 5
    return_type: str = BOOL


@dataclass(frozen=True)
class Not:
    """Logical NOT of boolean node."""
    node: Any  # Node[BOOL]
    return_type: str = BOOL


@dataclass(frozen=True)
class IfThenElse:
    """Conditional expression: condition ? then_node : else_node"""
    condition: Any  # Node[BOOL]
    then_node: Any  # Node[T]
    else_node: Any  # Node[T] (same type as then_node)
    return_type: str = FLOAT  # Will be determined by branches


# ────────────────────────────────────────────────────────────────────────────────
# CATEGORY 6: GATES & FILTERS
# ────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RegimeFilter:
    """Filter by market regime (e.g., 'trend_up', 'chop')."""
    regime_value: str  # Must match MarketRegime enum values
    return_type: str = BOOL


@dataclass(frozen=True)
class CostGate:
    """
    Cost gate: expected_profit >= cost_multiplier * estimated_cost
    
    MANDATORY in entry_condition (semantic validation).
    """
    expected_profit: Any  # Node[FLOAT]
    cost_multiplier: float  # K factor (e.g., 2.0 for trend, 3.0 for mean reversion)
    return_type: str = BOOL


@dataclass(frozen=True)
class TimeWindow:
    """Time window filter: now_ms in [start_ms, end_ms]."""
    start_ms: int
    end_ms: int
    return_type: str = BOOL


# ────────────────────────────────────────────────────────────────────────────────
# CATEGORY 7: ACTIONS
# ────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SignalEntry:
    """Entry signal with side and confidence."""
    side: str  # "BUY" or "SELL"
    confidence: float  # [0.0, 1.0]
    return_type: str = SIGNAL


@dataclass(frozen=True)
class SignalExit:
    """Exit signal with reason."""
    reason: str  # Human-readable exit reason
    return_type: str = SIGNAL


@dataclass(frozen=True)
class SizingFixed:
    """Fixed percentage sizing."""
    percent: float  # [0.1, 10.0] % of equity
    return_type: str = FLOAT


@dataclass(frozen=True)
class SizingATRBased:
    """ATR-based dynamic sizing."""
    atr_multiple: float  # Position size = ATR * multiple
    return_type: str = FLOAT


# ────────────────────────────────────────────────────────────────────────────────
# CATEGORY 8: ROOT NODE & EXIT PLAN
# ────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ExitPlanNode:
    """Exit plan specification."""
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    time_limit_ms: Optional[int] = None
    
    def __post_init__(self):
        """Validate at least one exit condition exists."""
        if not any([self.stop_loss_pct, self.take_profit_pct, self.time_limit_ms]):
            raise ValueError("ExitPlanNode requires at least one exit condition")


@dataclass(frozen=True)
class StrategyGenome:
    """
    Root node of the strategy AST.
    
    Represents a complete strategy genome that can be validated,
    evaluated, and evolved.
    """
    entry_condition: Any  # Node[BOOL] - when to enter
    exit_condition: Any  # Node[BOOL] - when to exit
    sizing_logic: Any  # Node[FLOAT] - position size
    exit_plan: ExitPlanNode  # Exit plan specification
    metadata: Dict[str, Any]  # strategy_id, name, description, etc.
    
    def __post_init__(self):
        """Basic validation on construction."""
        if not self.metadata.get("strategy_id"):
            raise ValueError("StrategyGenome.metadata must include 'strategy_id'")


# ────────────────────────────────────────────────────────────────────────────────
# TYPE UNION (for type checking)
# ────────────────────────────────────────────────────────────────────────────────

Node = Union[
    # Literals
    ConstFloat, ConstInt, ConstBool, ConstString,
    # Market Data
    PriceMid, PriceBid, PriceAsk, SpreadPct, Volume, VolatilityState,
    # Indicators
    SMA, EMA, RSI, ATR, Highest, Lowest, ROC,
    # Comparators
    GreaterThan, LessThan, Equal, CrossAbove, CrossBelow,
    # Boolean Logic
    And, Or, Not, IfThenElse,
    # Gates & Filters
    RegimeFilter, CostGate, TimeWindow,
    # Actions
    SignalEntry, SignalExit, SizingFixed, SizingATRBased,
    # Root
    StrategyGenome,
]


# ────────────────────────────────────────────────────────────────────────────────
# PHASE 11C: INTERPRETER TYPES (Evidence & Dimension)
# ────────────────────────────────────────────────────────────────────────────────


from enum import Enum


class Dimension(Enum):
    """Dimension classification for runtime dimension checking (Constitution §2.6)."""
    PRICE = "price"       # Prices (bid, ask, mid)
    OSC = "osc"          # Oscillators (RSI, normalized indicators)
    TIME = "time"        # Timestamps
    NONE = "none"        # Dimensionless (constants, booleans)


# Veto Flag Constants (stable, sorted by name)
class VetoFlag:
    """Constitutional violation and runtime veto flags."""
    CONSTITUTIONAL_VIOLATION = "CONSTITUTIONAL_VIOLATION"
    DIMENSION_MISMATCH = "DIMENSION_MISMATCH"
    MISSING_DATA = "MISSING_DATA"
    STEP_BUDGET = "STEP_BUDGET"


@dataclass(frozen=True)
class NodeEvidence:
    """
    Evidence of a single node evaluation.
    
    Streaming record appended during interpreter execution.
    """
    node_id: str
    node_type: str
    inputs: Dict[str, Any]       # Normalized floats (8 decimals)
    output: Any                   # Normalized float/bool/str
    pass_fail: Optional[bool]     # For boolean nodes
    severity: str                 # "INFO" | "WARN" | "BLOCK"
    is_fallback: bool
    fallback_reason: Optional[str]
    rationale: str                # ≤256 chars (hard truncated)
    timestamp_ms: int


@dataclass(frozen=True)
class DecisionEvidence:
    """
    Complete genome evaluation evidence.
    
    Deterministic output from interpreter.evaluate().
    """
    signal: str                           # "ENTRY" | "EXIT" | "NOOP"
    confidence_raw: float                 # Pre-bridge penalties (0.0-1.0)
    sizing_pct: float                     # Position size percentage
    veto_flags: List[str]                 # Sorted deterministically
    logic_trace: List[NodeEvidence]       # Execution order (matches execution_plan)
    fallback_count: int
    constitutional_violations: List[str]  # Sorted deterministically
    evaluated_node_count: int
    step_budget_used: int
    step_budget_limit: int
