"""
EPOCH E Phase E3: Risk Models
Deterministic, auditable risk quantification for capital preservation
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple, Literal

from pydantic import BaseModel, Field, validator


class RiskConfig(BaseModel):
    """
    Risk Engine configuration with strict validation
    
    LOCKED INVARIANTS:
    - Invalid config raises at initialization (fail-fast)
    - All limits are percentages (0.0 to 1.0)
    - Fail-closed defaults for all safety flags
    
    Philosophy: Conservative defaults, explicit overrides
    """
    
    # Exposure limits
    max_exposure_per_symbol: float = Field(0.20, description="Max exposure per symbol (0.0-1.0)")
    max_portfolio_exposure: float = Field(0.80, description="Max total portfolio exposure (0.0-1.0)")
    
    # Drawdown limit
    max_drawdown_limit: float = Field(0.15, description="Max drawdown from peak (0.0-1.0)")
    
    # VaR parameters
    var_confidence_level: float = Field(0.95, description="VaR confidence level (0.95 or 0.99 only)")
    var_horizon_days: int = Field(1, description="VaR time horizon in days")
    
    # Fail-closed flags
    fail_closed_on_missing_volatility: bool = Field(True, description="Block if volatility missing")
    allow_risk_without_size: bool = Field(False, description="Allow intents without sizing")
    
    # Optional safety parameters
    volatility_floor: float = Field(0.01, description="Minimum volatility (conservative floor)")
    correlation_default: float = Field(1.0, description="Default correlation assumption (conservative)")
    
    @validator('max_exposure_per_symbol', 'max_portfolio_exposure', 'max_drawdown_limit')
    def validate_percentage(cls, v):
        """Validate percentage fields are in [0, 1]"""
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"Must be between 0.0 and 1.0, got {v}")
        return v
    
    @validator('var_confidence_level')
    def validate_confidence_level(cls, v):
        """Only support 0.95 and 0.99 (deterministic z-scores)"""
        if v not in [0.95, 0.99]:
            raise ValueError(f"Only 0.95 and 0.99 supported, got {v}")
        return v
    
    @validator('var_horizon_days')
    def validate_horizon(cls, v):
        """Validate horizon is positive"""
        if v < 1:
            raise ValueError(f"Horizon must be >= 1 day, got {v}")
        return v
    
    @validator('volatility_floor')
    def validate_volatility_floor(cls, v):
        """Validate volatility floor is reasonable"""
        if not (0.0 < v < 1.0):
            raise ValueError(f"Volatility floor must be in (0, 1), got {v}")
        return v
    
    @validator('correlation_default')
    def validate_correlation(cls, v):
        """Validate correlation is in [-1, 1]"""
        if not (-1.0 <= v <= 1.0):
            raise ValueError(f"Correlation must be in [-1, 1], got {v}")
        return v


class Position(BaseModel):
    """
    Portfolio position
    
    Minimal model for risk calculations
    """
    symbol: str = Field(..., description="Trading pair")
    quantity: float = Field(..., description="Position size (signed: positive=LONG, negative=SHORT)")
    entry_price: Optional[float] = Field(None, description="Entry price (optional)")
    
    @property
    def side(self) -> Literal["LONG", "SHORT"]:
        """Position side derived from quantity sign"""
        return "LONG" if self.quantity >= 0 else "SHORT"
    
    @property
    def notional_value(self) -> float:
        """Absolute notional value (unsigned)"""
        return abs(self.quantity)


class RiskContext(BaseModel):
    """
    Portfolio state for risk assessment
    
    CRITICAL CONTRACT:
    - volatility_map MUST originate from:
      1. Epoch D2 rolling historical window
      2. External pre-computed feed
      3. Static constant (TESTING ONLY)
    
    Runtime inference is FORBIDDEN.
    
    Missing volatility with fail_closed_on_missing_volatility=True
    will cause RISK_MISSING_VOLATILITY blocking flag.
    """
    
    # Portfolio equity
    portfolio_equity: float = Field(..., description="Current portfolio equity (quote currency)")
    peak_equity: float = Field(..., description="Peak equity for drawdown calculation")
    
    # Positions
    open_positions: Dict[str, Position] = Field(default_factory=dict, description="Symbol -> Position")
    
    # Market data (REQUIRED)
    mark_prices: Dict[str, float] = Field(..., description="Symbol -> current mark price")
    
    # Volatility (STRICT CONTRACT - see docstring)
    volatility_map: Dict[str, float] = Field(
        default_factory=dict,
        description="Symbol -> annualized volatility (MUST be from D2 or external feed)"
    )
    
    # Optional correlation matrix
    correlation_map: Optional[Dict[Tuple[str, str], float]] = Field(
        None,
        description="(symbol1, symbol2) -> correlation [-1, 1]"
    )
    
    # Timestamp
    now_ms: Optional[int] = Field(None, description="Override timestamp (for deterministic tests)")
    
    @validator('portfolio_equity', 'peak_equity')
    def validate_positive(cls, v):
        """Validate equity values are positive"""
        if v <= 0:
            raise ValueError(f"Equity must be positive, got {v}")
        return v
    
    @validator('volatility_map')
    def validate_volatilities(cls, v):
        """Validate all volatilities are positive"""
        for symbol, vol in v.items():
            if vol <= 0 or not (0 < vol < 10):  # Sanity check: 0% to 1000% annualized
                raise ValueError(f"Invalid volatility for {symbol}: {vol}")
        return v


class RiskAssessment(BaseModel):
    """
    Risk assessment output
    
    STRICT FLAG SEMANTICS:
    - blocking_flags: Cause is_safe=False, Governance MUST reject
    - warnings: Informational only, Governance MAY react
    
    is_safe = len(blocking_flags) == 0
    
    ALL assumptions must be explicit (no implicit defaults in audit).
    """
    
    # Intent identification
    intent_id: str = Field(..., description="Intent identifier")
    strategy_id: str = Field(..., description="Strategy identifier")
    symbol: str = Field(..., description="Trading pair")
    
    # Safety determination
    is_safe: bool = Field(..., description="True if no blocking flags")
    
    # Metrics (all must be present)
    metrics: Dict[str, float] = Field(..., description="Risk metrics (exposure, drawdown, VaR)")
    
    # Flags (STRICT SEMANTICS)
    blocking_flags: List[str] = Field(default_factory=list, description="Flags that BLOCK execution")
    warnings: List[str] = Field(default_factory=list, description="Informational warnings")
    
    # Assumptions (MANDATORY for audit)
    assumptions: Dict[str, str] = Field(..., description="Explicit assumptions (correlation, model, etc.)")
    
    # Timestamp
    computed_at_ms: int = Field(default_factory=lambda: int(time.time() * 1000), description="Computation timestamp")
    
    @validator('is_safe', always=True)
    def validate_is_safe(cls, v, values):
        """is_safe MUST be False if blocking_flags present"""
        if 'blocking_flags' in values:
            expected_safe = len(values['blocking_flags']) == 0
            if v != expected_safe:
                raise ValueError(f"is_safe={v} inconsistent with blocking_flags={values['blocking_flags']}")
        return v


# Standard blocking flags (machine-readable)
class RiskBlockingFlags:
    """Standard blocking flag constants"""
    
    # Input validation
    EQUITY_INVALID = "RISK_EQUITY_INVALID"
    PEAK_EQUITY_INVALID = "RISK_PEAK_EQUITY_INVALID"
    MISSING_MARK_PRICE = "RISK_MISSING_MARK_PRICE"
    MISSING_VOLATILITY = "RISK_MISSING_VOLATILITY"
    UNDEFINED_INTENT_SIZE = "RISK_UNDEFINED_INTENT_SIZE"
    
    # Math failures
    MATH_INVALID = "RISK_MATH_INVALID"
    UNSUPPORTED_CONFIDENCE = "RISK_UNSUPPORTED_CONFIDENCE"
    
    # Breach flags
    EXPOSURE_SYMBOL_BREACH = "RISK_EXPOSURE_SYMBOL_BREACH"
    EXPOSURE_PORTFOLIO_BREACH = "RISK_EXPOSURE_PORTFOLIO_BREACH"
    DRAWDOWN_BREACH = "RISK_DRAWDOWN_BREACH"
    VAR_BREACH = "RISK_VAR_BREACH"


# Standard warning flags (informational)
class RiskWarningFlags:
    """Standard warning flag constants"""
    
    EXPOSURE_NEAR_LIMIT = "RISK_EXPOSURE_NEAR_LIMIT"
    VOLATILITY_HIGH = "RISK_VOLATILITY_HIGH"
    CORRELATION_ASSUMED = "RISK_CORRELATION_ASSUMED"
