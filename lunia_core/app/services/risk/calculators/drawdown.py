"""
EPOCH E Phase E3: Drawdown Calculator
Deterministic drawdown calculation
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from ..models import RiskContext, RiskConfig, RiskBlockingFlags


def calculate_drawdown(
    context: RiskContext,
    config: RiskConfig
) -> Tuple[Dict[str, float], List[str]]:
    """
    Calculate portfolio drawdown from peak
    
    Formula:
        drawdown_pct = (peak_equity - current_equity) / peak_equity
    
    Returns:
        (metrics_dict, blocking_flags_list)
    
    Metrics:
    - drawdown_pct
    
    Blocking flags:
    - RISK_PEAK_EQUITY_INVALID (if peak <= 0)
    - RISK_EQUITY_INVALID (if current equity <= 0)
    - RISK_DRAWDOWN_BREACH (if drawdown exceeds limit)
    """
    metrics = {}
    flags = []
    
    # Validate inputs
    if context.peak_equity <= 0:
        flags.append(RiskBlockingFlags.PEAK_EQUITY_INVALID)
        return (metrics, flags)
    
    if context.portfolio_equity <= 0:
        flags.append(RiskBlockingFlags.EQUITY_INVALID)
        return (metrics, flags)
    
    # Calculate drawdown
    drawdown_pct = (context.peak_equity - context.portfolio_equity) / context.peak_equity
    
    # Clamp to [0, 1] (drawdown cannot be negative or > 100%)
    drawdown_pct = max(0.0, min(1.0, drawdown_pct))
    
    metrics['drawdown_pct'] = drawdown_pct
    
    # Check breach
    if drawdown_pct > config.max_drawdown_limit:
        flags.append(RiskBlockingFlags.DRAWDOWN_BREACH)
    
    return (metrics, flags)
