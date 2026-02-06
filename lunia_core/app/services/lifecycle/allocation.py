"""
Allocation Engine — Deterministic Position Sizing

Calculates entry sizes based on:
- Total equity
- Strategy confidence [0.0, 1.0]
- Volatility regime (LOW, NORMAL, HIGH)
- Allocation policy
"""
from typing import Optional

from lunia_core.app.services.lifecycle.models import AllocationPolicy, VolatilityRegime


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp value to [min_val, max_val]"""
    return max(min_val, min(value, max_val))


class AllocationEngine:
    """
    Deterministic capital allocation calculator.
    
    Formula:
        1. Base = equity * base_unit_pct
        2. Confidence multiplier = clamp(1.0 + (confidence - 0.5) * 2.0, 0.5, max_scale)
        3. Volatility scalar = {0.5 (HIGH), 1.0 (NORMAL), 1.2 (LOW)}
        4. Final = Base * Confidence * Volatility
        5. If Final < min_notional → None (ABORT)
    
    DETERMINISTIC: Same inputs → same output (no randomness)
    FAIL-CLOSED: Missing inputs → None
    """
    
    def __init__(self, policy: AllocationPolicy):
        self.policy = policy
    
    def calculate_entry_size(
        self,
        total_equity: float,
        strategy_confidence: float,
        volatility_regime: VolatilityRegime,
        reference_price: float,
    ) -> Optional[float]:
        """
        Calculate position quantity (base currency).
        
        Args:
            total_equity: Total account equity in quote currency
            strategy_confidence: Strategy confidence score [0.0, 1.0]
            volatility_regime: Current market volatility
            reference_price: Current market price
        
        Returns:
            Position quantity in base currency, or None if below minimum
        
        Raises:
            ValueError: If inputs are invalid
        """
        # Validation
        if total_equity <= 0:
            raise ValueError(f"Invalid total_equity: {total_equity}")
        
        if not (0.0 <= strategy_confidence <= 1.0):
            raise ValueError(f"Invalid confidence: {strategy_confidence}")
        
        if reference_price <= 0:
            raise ValueError(f"Invalid reference_price: {reference_price}")
        
        # 1. Base notional
        raw_notional = total_equity * self.policy.base_unit_pct
        
        # 2. Confidence multiplier
        # confidence=0.5 → 1.0x (neutral)
        # confidence=1.0 → max_scale_factor (high confidence)
        # confidence=0.0 → 0.5x (low confidence, minimum 50%)
        conf_mult = clamp(
            1.0 + (strategy_confidence - 0.5) * 2.0,
            0.5,
            self.policy.max_scale_factor
        )
        
        # 3. Volatility scalar
        if self.policy.volatility_scalar_enabled:
            if volatility_regime == VolatilityRegime.HIGH:
                vol_scalar = 0.5  # Cut size in half
            elif volatility_regime == VolatilityRegime.LOW:
                vol_scalar = 1.2  # Increase size by 20%
            else:  # NORMAL
                vol_scalar = 1.0
        else:
            vol_scalar = 1.0
        
        # 4. Final notional
        final_notional = raw_notional * conf_mult * vol_scalar
        
        # 5. Floor check
        if final_notional < self.policy.min_notional_value:
            return None  # ABORT: Too small
        
        # 6. Convert to quantity
        quantity = final_notional / reference_price
        
        return quantity
    
    def get_sizing_breakdown(
        self,
        total_equity: float,
        strategy_confidence: float,
        volatility_regime: VolatilityRegime,
        reference_price: float,
    ) -> dict:
        """
        Get detailed sizing breakdown for audit/debugging.
        
        Returns breakdown dict showing each calculation step.
        """
        raw_notional = total_equity * self.policy.base_unit_pct
        
        conf_mult = clamp(
            1.0 + (strategy_confidence - 0.5) * 2.0,
            0.5,
            self.policy.max_scale_factor
        )
        
        if self.policy.volatility_scalar_enabled:
            if volatility_regime == VolatilityRegime.HIGH:
                vol_scalar = 0.5
            elif volatility_regime == VolatilityRegime.LOW:
                vol_scalar = 1.2
            else:
                vol_scalar = 1.0
        else:
            vol_scalar = 1.0
        
        final_notional = raw_notional * conf_mult * vol_scalar
        quantity = final_notional / reference_price if final_notional >= self.policy.min_notional_value else None
        
        return {
            "total_equity": total_equity,
            "base_unit_pct": self.policy.base_unit_pct,
            "raw_notional": raw_notional,
            "confidence": strategy_confidence,
            "confidence_multiplier": conf_mult,
            "volatility_regime": volatility_regime.value,
            "volatility_scalar": vol_scalar,
            "final_notional": final_notional,
            "min_notional": self.policy.min_notional_value,
            "reference_price": reference_price,
            "quantity": quantity,
            "aborted": quantity is None,
        }
