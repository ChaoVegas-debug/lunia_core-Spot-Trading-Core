"""
Lifecycle Data Models

Defines immutable data contracts for capital allocation and exit management.
"""
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class VolatilityRegime(str, Enum):
    """Market volatility classification"""
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"


class AllocationPolicy(BaseModel):
    """
    Capital allocation configuration.
    
    Controls how position sizes are calculated based on:
    - Base unit (% of equity)
    - Confidence scaling
    - Volatility adjustment
    """
    
    base_unit_pct: float = Field(
        default=0.01,
        ge=0.001,
        le=0.10,
        description="Base position size as % of equity (default 1%)"
    )
    
    max_scale_factor: float = Field(
        default=2.5,
        ge=1.0,
        le=5.0,
        description="Maximum confidence multiplier"
    )
    
    min_notional_value: float = Field(
        default=10.0,
        ge=1.0,
        description="Minimum position size in quote currency (floor)"
    )
    
    volatility_scalar_enabled: bool = Field(
        default=True,
        description="Enable volatility-based size adjustment"
    )
    
    class Config:
        frozen = True


class ExitPlan(BaseModel):
    """
    Immutable exit plan for a position.
    
    Defines HOW a position MUST exit via:
    - Stop loss (risk management)
    - Take profit (profit target)
    - Trailing stop (trend following)
    - Time expiry (regime invalidation)
    
    MANDATORY: Position without ExitPlan is INVALID.
    """
    
    # Position identification
    position_id: str = Field(description="Unique position identifier")
    symbol: str = Field(description="Trading symbol (e.g. BTCUSDT)")
    side: str = Field(description="Position direction: LONG or SHORT")
    entry_price: float = Field(gt=0, description="Position entry price")
    
    # Exit triggers (at least one must be set)
    stop_loss_price: Optional[float] = Field(
        default=None,
        description="Price at which to exit for loss prevention"
    )
    
    take_profit_price: Optional[float] = Field(
        default=None,
        description="Price at which to exit for profit taking"
    )
    
    trailing_stop_activation_price: Optional[float] = Field(
        default=None,
        description="Price at which trailing stop activates"
    )
    
    trailing_stop_callback_pct: Optional[float] = Field(
        default=None,
        ge=0.001,
        le=0.10,
        description="Trailing stop callback % from peak"
    )
    
    max_duration_ms: Optional[int] = Field(
        default=None,
        gt=0,
        description="Maximum position age in milliseconds"
    )
    
    # Metadata
    created_at_ms: int = Field(description="Plan creation timestamp")
    last_updated_ms: int = Field(description="Last modification timestamp")
    strategy_type: str = Field(description="TREND, MEAN_REVERSION, or BREAKOUT")
    
    # Trailing stop state (mutable via copy)
    trailing_stop_peak_price: Optional[float] = Field(
        default=None,
        description="Highest price seen for trailing stop (LONG) or lowest (SHORT)"
    )
    
    class Config:
        frozen = True
        use_enum_values = True
    
    def with_updated_trailing_stop(
        self,
        new_peak_price: float,
        new_stop_loss: float,
        now_ms: int
    ) -> "ExitPlan":
        """
        Create updated plan with new trailing stop state.
        
        Returns new ExitPlan instance (immutability preserved).
        """
        return self.copy(
            update={
                "trailing_stop_peak_price": new_peak_price,
                "stop_loss_price": new_stop_loss,
                "last_updated_ms": now_ms,
            }
        )
