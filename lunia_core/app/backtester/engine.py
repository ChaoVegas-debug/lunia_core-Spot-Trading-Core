"""Backtest engine placeholder."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    returns: List[float]
    win_rate: float


class BacktestEngine:
    """Skeleton backtest engine."""

    def run(self) -> BacktestResult:
        logger.info("Running backtest (placeholder)")
        return BacktestResult(returns=[], win_rate=0.0)
