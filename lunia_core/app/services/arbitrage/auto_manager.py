"""Auto-mode manager for arbitrage execution."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable, Optional

from app.core.state import get_state

from .scanner import ArbitrageFilters, ArbitrageOpportunity
from .strategy import ArbitrageStrategy, StrategyDecision

logger = logging.getLogger(__name__)


@dataclass
class AutoResult:
    decision: StrategyDecision
    executed: bool


class ArbitrageAutoManager:
    """Runs periodic scans & executions when auto mode is enabled."""

    def __init__(
        self,
        scanner_callback: Callable[[ArbitrageFilters], list[ArbitrageOpportunity]],
        executor_callback: Callable[[ArbitrageOpportunity], None],
        strategy: Optional[ArbitrageStrategy] = None,
    ) -> None:
        self._scanner = scanner_callback
        self._executor = executor_callback
        self._strategy = strategy or ArbitrageStrategy()
        self._last_run: float = 0.0

    def maybe_run(self, filters: ArbitrageFilters) -> AutoResult:
        state = get_state()
        if state.get("global_stop") or not state.get("arb_on", True):
            logger.info("auto arbitrage skipped due to global stop/arb_off")
            return AutoResult(decision=StrategyDecision(None, "stopped"), executed=False)
        if not state.get("arb", {}).get("auto_mode", False):
            return AutoResult(decision=StrategyDecision(None, "auto_disabled"), executed=False)
        now = time.time()
        interval = max(5, int(state.get("arb", {}).get("interval", 60)))
        if now - self._last_run < interval:
            return AutoResult(decision=StrategyDecision(None, "interval_wait"), executed=False)
        opportunities = self._scanner(filters)
        decision = self._strategy.select(opportunities, filters)
        if decision.opportunity is None:
            self._last_run = now
            return AutoResult(decision=decision, executed=False)
        self._executor(decision.opportunity)
        self._last_run = time.time()
        return AutoResult(decision=decision, executed=True)


__all__ = ["ArbitrageAutoManager", "AutoResult"]
