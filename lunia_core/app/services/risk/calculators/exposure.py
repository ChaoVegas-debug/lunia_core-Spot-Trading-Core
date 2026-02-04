"""
EPOCH E Phase E3: Exposure Calculator
Deterministic portfolio exposure calculations
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

from ..models import Position, RiskContext, RiskConfig, RiskBlockingFlags
from lunia_core.app.services.strategy.models import IntentProposal


def calculate_exposure(
    context: RiskContext,
    intent: IntentProposal | None,
    config: RiskConfig
) -> Tuple[Dict[str, float], List[str]]:
    """
    Calculate current and projected portfolio exposure
    
    Returns:
        (metrics_dict, blocking_flags_list)
    
    Metrics include:
    - current_symbol_exposure_pct
    - projected_symbol_exposure_pct (if intent sized)
    - current_portfolio_exposure_pct
    - projected_portfolio_exposure_pct (if intent sized)
    
    Blocking flags:
    - RISK_EQUITY_INVALID (if equity <= 0)
    - RISK_MISSING_MARK_PRICE (if mark price missing for any position)
    - RISK_UNDEFINED_INTENT_SIZE (if intent not sized and allow_risk_without_size=False)
    - RISK_EXPOSURE_SYMBOL_BREACH
    - RISK_EXPOSURE_PORTFOLIO_BREACH
    """
    metrics = {}
    flags = []
    
    # Validate equity
    if context.portfolio_equity <= 0:
        flags.append(RiskBlockingFlags.EQUITY_INVALID)
        return (metrics, flags)
    
    # Calculate current portfolio notional
    portfolio_notional = 0.0
    for symbol, position in context.open_positions.items():
        mark_price = context.mark_prices.get(symbol)
        
        if mark_price is None or not math.isfinite(mark_price) or mark_price <= 0:
            flags.append(RiskBlockingFlags.MISSING_MARK_PRICE)
            return (metrics, flags)
        
        notional = abs(position.quantity) * mark_price
        portfolio_notional += notional
    
    # Current portfolio exposure
    current_portfolio_exposure_pct = portfolio_notional / context.portfolio_equity
    metrics['current_portfolio_exposure_pct'] = current_portfolio_exposure_pct
    
    # Current symbol exposure (if intent specified)
    if intent:
        symbol = intent.symbol
        current_position = context.open_positions.get(symbol)
        
        if current_position:
            mark_price = context.mark_prices.get(symbol)
            if mark_price is None:
                flags.append(RiskBlockingFlags.MISSING_MARK_PRICE)
                return (metrics, flags)
            
            symbol_notional = abs(current_position.quantity) * mark_price
            current_symbol_exposure_pct = symbol_notional / context.portfolio_equity
            metrics['current_symbol_exposure_pct'] = current_symbol_exposure_pct
        else:
            metrics['current_symbol_exposure_pct'] = 0.0
        
        # Projected exposure (CRITICAL: requires intent sizing)
        # For E3, we assume intent has no sizing yet (common at strategy→governance stage)
        # If allow_risk_without_size=False → BLOCK
        
        if not config.allow_risk_without_size:
            # Intent must have sizing to compute projected exposure
            # Since IntentProposal (E1/E2) typically has no quantity field yet,
            # we BLOCK by default for capital safety
            flags.append(RiskBlockingFlags.UNDEFINED_INTENT_SIZE)
            # Still return current metrics for audit
        else:
            # If explicitly allowed, set projected = current (conservative assumption)
            metrics['projected_symbol_exposure_pct'] = metrics['current_symbol_exposure_pct']
            metrics['projected_portfolio_exposure_pct'] = current_portfolio_exposure_pct
    else:
        # No intent → no projected metrics
        metrics['current_symbol_exposure_pct'] = 0.0
    
    # Check exposure breaches (only for current, since projected requires sizing)
    if intent and 'current_symbol_exposure_pct' in metrics:
        if metrics['current_symbol_exposure_pct'] > config.max_exposure_per_symbol:
            flags.append(RiskBlockingFlags.EXPOSURE_SYMBOL_BREACH)
    
    if current_portfolio_exposure_pct > config.max_portfolio_exposure:
        flags.append(RiskBlockingFlags.EXPOSURE_PORTFOLIO_BREACH)
    
    return (metrics, flags)
