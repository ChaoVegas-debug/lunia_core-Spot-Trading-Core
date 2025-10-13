"""Selection policy for arbitrage execution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .scanner import ArbitrageFilters, ArbitrageOpportunity


@dataclass
class StrategyDecision:
    """Represents the policy output for a scan."""

    opportunity: Optional[ArbitrageOpportunity]
    reason: str


class ArbitrageStrategy:
    """Very small policy wrapper to choose an opportunity for execution."""

    def select(
        self,
        opportunities: List[ArbitrageOpportunity],
        filters: ArbitrageFilters,
    ) -> StrategyDecision:
        if not opportunities:
            return StrategyDecision(opportunity=None, reason="no_opportunities")
        target = opportunities[0]
        if target.net_roi_pct < filters.min_net_roi_pct:
            return StrategyDecision(opportunity=None, reason="roi_below_threshold")
        if target.net_profit_usd < filters.min_net_usd:
            return StrategyDecision(opportunity=None, reason="profit_below_threshold")
        return StrategyDecision(opportunity=target, reason="ok")


__all__ = ["ArbitrageStrategy", "StrategyDecision"]
