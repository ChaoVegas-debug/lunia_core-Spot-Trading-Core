"""
PHASE 14A — EXECUTION GATEWAY: Models

Deterministic data contracts for execution governance.

CRITICAL RULES:
- Frozen dataclasses (immutable)
- Fail-closed validation
- Deterministic JSON serialization
- No wall-clock usage
"""

import json
from dataclasses import dataclass, asdict
from decimal import Decimal
from typing import Dict, Any, Optional, Literal, FrozenSet


# ────────────────────────────────────────────────────────────────────────────────
# TYPE ALIASES
# ────────────────────────────────────────────────────────────────────────────────

DecisionStatus = Literal["BLOCKED", "ALLOWED"]


# ────────────────────────────────────────────────────────────────────────────────
# RISK LIMITS (Frozen)
# ────────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RiskLimits:
    """
    Immutable risk limits for pre-trade checks.
    
    All numeric limits must be >= 0.
    allowed_symbols must be non-empty (empty = deny all for safety).
    Symbols in allowed_symbols should be pre-normalized (Binance-style: BTCUSDT).
    """
    max_order_notional: Decimal
    max_daily_loss: Decimal
    max_position_size: Decimal
    allowed_symbols: FrozenSet[str]
    warn_dd_pct: Decimal = Decimal("0.05")  # 5% default
    crit_dd_pct: Decimal = Decimal("0.10")  # 10% default
    
    def __post_init__(self):
        """Validate limits (fail-closed)."""
        # Validate numeric limits
        if self.max_order_notional < 0:
            raise ValueError("max_order_notional must be >= 0")
        if self.max_daily_loss < 0:
            raise ValueError("max_daily_loss must be >= 0")
        if self.max_position_size < 0:
            raise ValueError("max_position_size must be >= 0")
        if self.warn_dd_pct < 0:
            raise ValueError("warn_dd_pct must be >= 0")
        if self.crit_dd_pct < 0:
            raise ValueError("crit_dd_pct must be >= 0")
        
        # Validate allowed_symbols (empty = deny all for safety)
        # This is intentional: explicit allowlist required
        # No validation error, but documented behavior


# ────────────────────────────────────────────────────────────────────────────────
# EXECUTION CONTEXT SNAPSHOT (Read-Only Input Bundle)
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class ExecutionContextSnapshot:
    """
    Read-only snapshot of system state for execution evaluation.
    
    Avoids circular imports by accepting dicts instead of live objects.
    Gateway must not mutate or call methods on external components.
    
    Fields:
    - snapshot: MarketSnapshot dict (from live_data_pump)
    - portfolio_state: PortfolioState dict (from virtual_portfolio)
    - system_health: SystemHealth dict (from hud_api)
    - ts_ms: Optional precomputed canonical timestamp
    """
    snapshot: Optional[Dict[str, Any]]
    portfolio_state: Optional[Dict[str, Any]]
    system_health: Optional[Dict[str, Any]]
    ts_ms: Optional[int] = None


# ────────────────────────────────────────────────────────────────────────────────
# EXECUTION REQUEST
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class ExecutionRequest:
    """
    Request to evaluate strategy intent for execution.
    
    Fields:
    - intent: StrategyIntent dict (from shadow_mode)
    - symbol: Raw symbol string (will be normalized by gateway)
    - ts_ms: Optional timestamp (for canonical timestamp computation)
    """
    intent: Dict[str, Any]
    symbol: str
    ts_ms: Optional[int] = None


# ────────────────────────────────────────────────────────────────────────────────
# EXECUTION DECISION
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class ExecutionDecision:
    """
    Result of execution gateway evaluation.
    
    Fields:
    - status: BLOCKED or ALLOWED
    - reason_code: Check code (KS_001, ARM_002, etc.) or "OK"
    - reason_message: Human-readable explanation
    - checks_passed: Dict of all check IDs to pass/fail status
    - ts_ms: Canonical timestamp
    - normalized_symbol: Binance-style normalized symbol
    - error: Error details if exception occurred
    """
    status: DecisionStatus
    reason_code: str
    reason_message: str
    checks_passed: Dict[str, bool]
    ts_ms: Optional[int]
    normalized_symbol: str
    error: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return asdict(self)


# ────────────────────────────────────────────────────────────────────────────────
# KILL SWITCH STATE
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class KillSwitchState:
    """
    Kill switch state (absolute veto power).
    
    Fields:
    - enabled: If True, ALL requests are blocked
    - reason: Explanation for kill switch status
    - ts_ms: Timestamp of last state change
    """
    enabled: bool
    reason: Optional[str] = None
    ts_ms: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return asdict(self)


# ────────────────────────────────────────────────────────────────────────────────
# AUDIT PAYLOAD
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class AuditPayload:
    """
    Audit record for execution gateway evaluation (decoupled).
    
    Gateway returns this; caller decides where to persist.
    
    Fields:
    - schema_version: Audit schema version
    - phase: Phase identifier (14A)
    - event: Event type (EXECUTION_GATEWAY_EVALUATED)
    - timestamp_ms: Canonical timestamp
    - symbol: Normalized symbol
    - data: Nested data (decision, context_digest, checks_detail)
    """
    schema_version: str
    phase: str
    event: str
    timestamp_ms: Optional[int]
    symbol: str
    data: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return asdict(self)


# ────────────────────────────────────────────────────────────────────────────────
# HELPERS
# ────────────────────────────────────────────────────────────────────────────────

def stable_json(obj: Any) -> str:
    """
    Canonical JSON serialization (deterministic).
    
    Args:
        obj: Object to serialize
    
    Returns:
        Canonical JSON string (sorted keys, compact)
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def canonical_ts(*candidates: Optional[int]) -> Optional[int]:
    """
    Compute canonical timestamp from candidates (deterministic).
    
    Returns max of all non-None timestamps, or None if all None.
    
    Args:
        *candidates: Timestamp candidates (may be None)
    
    Returns:
        Max timestamp or None
    """
    valid = [ts for ts in candidates if ts is not None]
    return max(valid) if valid else None


def normalize_symbol(raw_symbol: str) -> str:
    """
    Normalize symbol to Binance-style (deterministic).
    
    Rules:
    - Uppercase
    - Remove separators: -, /, :
    
    Examples:
    - btc/usdt -> BTCUSDT
    - BTC-USDT -> BTCUSDT
    - btcusdt -> BTCUSDT
    
    Args:
        raw_symbol: Raw symbol string
    
    Returns:
        Normalized symbol
    
    Raises:
        ValueError: If normalized symbol is empty/invalid
    """
    normalized = raw_symbol.upper().replace("-", "").replace("/", "").replace(":", "")
    
    if not normalized or not normalized.strip():
        raise ValueError(f"Invalid symbol after normalization: {raw_symbol}")
    
    return normalized


def safe_decimal(value: Any) -> Optional[Decimal]:
    """
    Safe Decimal parsing (fail-safe).
    
    Args:
        value: Value to parse (str, int, float, Decimal)
    
    Returns:
        Decimal or None if parsing fails
    """
    if value is None:
        return None
    
    if isinstance(value, Decimal):
        return value
    
    try:
        return Decimal(str(value))
    except Exception:
        return None
