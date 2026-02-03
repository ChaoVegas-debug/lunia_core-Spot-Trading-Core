"""
EPOCH E Phase E3: Parametric VaR Calculator
Deterministic Value-at-Risk using parametric (normal) model
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

from ..models import RiskContext, RiskConfig, RiskBlockingFlags, Position


# Deterministic Z-scores for standard confidence levels
Z_SCORES = {
    0.95: 1.645,  # 95% confidence (one-tailed)
    0.99: 2.326,  # 99% confidence (one-tailed)
}


def calculate_var(
    context: RiskContext,
    config: RiskConfig
) -> Tuple[Dict[str, float], List[str]]:
    """
    Calculate Parametric VaR (assuming normal distribution)
    
    Formula (per symbol):
        sigma_horizon = annualized_vol * sqrt(horizon_days / 252)
        VaR_abs = notional_value * sigma_horizon * z_score
    
    Portfolio VaR (conservative, no correlation):
        portfolio_var_abs = sum(symbol_var_abs)
    
    Returns:
        (metrics_dict, blocking_flags_list)
    
    Metrics:
    - var_symbol_abs (if intent specified)
    - var_portfolio_abs
    
    Blocking flags:
    - RISK_MISSING_VOLATILITY (if volatility missing for any position)
    - RISK_MISSING_MARK_PRICE (if mark price missing)
    - RISK_UNSUPPORTED_CONFIDENCE (if confidence level not in Z_SCORES)
    - RISK_MATH_INVALID (if calculation produces NaN/Inf)
    """
    metrics = {}
    flags = []
    
    # Validate confidence level
    confidence = config.var_confidence_level
    if confidence not in Z_SCORES:
        flags.append(RiskBlockingFlags.UNSUPPORTED_CONFIDENCE)
        return (metrics, flags)
    
    z_score = Z_SCORES[confidence]
    
    # Calculate horizon volatility scaling factor
    # sigma_horizon = sigma_annual * sqrt(horizon / 252)
    horizon_factor = math.sqrt(config.var_horizon_days / 252.0)
    
    # Calculate VaR for each position
    portfolio_var_abs = 0.0
    
    for symbol, position in context.open_positions.items():
        # Get mark price
        mark_price = context.mark_prices.get(symbol)
        if mark_price is None or not math.isfinite(mark_price) or mark_price <= 0:
            flags.append(RiskBlockingFlags.MISSING_MARK_PRICE)
            return (metrics, flags)
        
        # Get volatility
        volatility = context.volatility_map.get(symbol)
        
        if volatility is None:
            if config.fail_closed_on_missing_volatility:
                flags.append(RiskBlockingFlags.MISSING_VOLATILITY)
                return (metrics, flags)
            else:
                # Use volatility floor if allowed
                volatility = config.volatility_floor
        
        # Apply volatility floor
        volatility = max(volatility, config.volatility_floor)
        
        # Calculate notional
        notional = abs(position.quantity) * mark_price
        
        # Calculate horizon volatility
        sigma_horizon = volatility * horizon_factor
        
        # Calculate VaR for this position
        var_abs = notional * sigma_horizon * z_score
        
        # Validate result
        if not math.isfinite(var_abs):
            flags.append(RiskBlockingFlags.MATH_INVALID)
            return (metrics, flags)
        
        # Accumulate (conservative: sum, assumes correlation=1.0)
        portfolio_var_abs += var_abs
    
    # Store metrics
    metrics['var_portfolio_abs'] = portfolio_var_abs
    metrics['var_symbol_abs'] = 0.0  # Default (no specific symbol VaR unless requested)
    
    return (metrics, flags)
