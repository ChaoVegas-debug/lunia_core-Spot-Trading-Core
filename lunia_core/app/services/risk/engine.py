"""
EPOCH E Phase E3: Risk Engine
Deterministic risk quantification orchestrator
"""
from __future__ import annotations

import logging
from typing import Optional

from .models import (
    RiskConfig,
    RiskContext,
    RiskAssessment,
    RiskBlockingFlags,
    RiskWarningFlags
)
from .calculators.exposure import calculate_exposure
from .calculators.drawdown import calculate_drawdown
from .calculators.var import calculate_var

from app.services.strategy.models import IntentProposal


logger = logging.getLogger(__name__)


class RiskEngine:
    """
    Risk Engine - The Immune System
    
    Responsibilities:
    - Accept IntentProposal + RiskContext
    - Compute deterministic risk metrics (exposure, drawdown, VaR)
    - Classify violations as blocking_flags or warnings
    - Produce RiskAssessment with explicit assumptions
    
    LOCKED INVARIANTS:
    - NO EXECUTION AUTHORITY (only computes, never executes)
    - FAIL-CLOSED ON UNCERTAINTY (missing data → blocking flag)
    - DETERMINISTIC (same inputs → same outputs)
    - AUDIT-FIRST (all assumptions explicit)
    
    Philosophy:
        Risk quantifies reality. Governance decides policy.
    """
    
    def __init__(self, config: RiskConfig):
        """
        Initialize risk engine
        
        Args:
            config: RiskConfig (validated at construction)
        """
        self.config = config
        logger.info(f"RiskEngine initialized with config: {config.dict()}")
    
    def assess(
        self,
        intent: IntentProposal,
        context: RiskContext
    ) -> RiskAssessment:
        """
        Assess risk for an intent proposal
        
        CRITICAL EXECUTION ORDER:
        1. Validate inputs (fail-closed)
        2. Run calculators (exposure, drawdown, VaR)
        3. Collect all flags
        4. Classify flags (blocking vs warnings)
        5. Build assumptions dict
        6. Construct RiskAssessment
        
        Args:
            intent: IntentProposal from strategy
            context: RiskContext (portfolio state)
        
        Returns:
            RiskAssessment with is_safe, metrics, flags, assumptions
        """
        # Step 1: Initialize accumulators
        all_metrics = {}
        all_blocking_flags = []
        all_warnings = []
        
        # Step 2: Calculate exposure
        exposure_metrics, exposure_flags = calculate_exposure(context, intent, self.config)
        all_metrics.update(exposure_metrics)
        all_blocking_flags.extend(exposure_flags)
        
        # Step 3: Calculate drawdown
        drawdown_metrics, drawdown_flags = calculate_drawdown(context, self.config)
        all_metrics.update(drawdown_metrics)
        all_blocking_flags.extend(drawdown_flags)
        
        # Step 4: Calculate VaR
        var_metrics, var_flags = calculate_var(context, self.config)
        all_metrics.update(var_metrics)
        all_blocking_flags.extend(var_flags)
        
        # Step 5: Add equity to metrics (for audit)
        all_metrics['equity'] = context.portfolio_equity
        all_metrics['peak_equity'] = context.peak_equity
        
        # Step 6: Generate warnings (informational only, do not block)
        # Example: exposure near limit (>90% of max)
        if 'current_portfolio_exposure_pct' in all_metrics:
            if all_metrics['current_portfolio_exposure_pct'] > self.config.max_portfolio_exposure * 0.9:
                if RiskBlockingFlags.EXPOSURE_PORTFOLIO_BREACH not in all_blocking_flags:
                    all_warnings.append(RiskWarningFlags.EXPOSURE_NEAR_LIMIT)
        
        # If correlation not provided, note assumption
        if context.correlation_map is None:
            all_warnings.append(RiskWarningFlags.CORRELATION_ASSUMED)
        
        # Step 7: Build assumptions dict (MANDATORY for audit)
        assumptions = {
            "model": "Parametric VaR (Normal Distribution)",
            "var_confidence": str(self.config.var_confidence_level),
            "var_horizon_days": str(self.config.var_horizon_days),
            "correlation_default": str(self.config.correlation_default),
            "volatility_floor": str(self.config.volatility_floor),
        }
        
        # Add volatility source assumption (CRITICAL)
        if context.volatility_map:
            assumptions["volatility_source"] = "RiskContext.volatility_map (D2 or external feed)"
        else:
            assumptions["volatility_source"] = "NONE (fail-closed if required)"
        
        # Step 8: Determine is_safe
        # STRICT SEMANTICS: is_safe = (no blocking flags)
        is_safe = len(all_blocking_flags) == 0
        
        # Step 9: Construct RiskAssessment
        assessment = RiskAssessment(
            intent_id=f"{intent.strategy_id}_{intent.symbol}_{intent.created_at_ms}",
            strategy_id=intent.strategy_id,
            symbol=intent.symbol,
            is_safe=is_safe,
            metrics=all_metrics,
            blocking_flags=all_blocking_flags,
            warnings=all_warnings,
            assumptions=assumptions
        )
        
        # Log assessment
        logger.info(
            f"Risk assessment complete: {intent.strategy_id} {intent.symbol} "
            f"is_safe={is_safe} blocking_flags={all_blocking_flags} warnings={all_warnings}"
        )
        
        return assessment
