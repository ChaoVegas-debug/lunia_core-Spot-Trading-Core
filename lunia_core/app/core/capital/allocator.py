"""Capital allocation helpers for spot strategies."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Iterable, Mapping

from ..metrics import (
    equity_total_usd,
    ops_capital_cap_pct,
    spot_alloc_strategy_usd,
    tradable_equity_usd,
)

logger = logging.getLogger(__name__)


@dataclass
class AllocationResult:
    tradable_equity: float
    per_strategy: Dict[str, float]


class CapitalAllocator:
    """Allocate capital budgets across strategies respecting caps."""

    def __init__(
        self,
        *,
        max_trade_pct: float,
        risk_per_trade_pct: float,
        max_symbol_exposure_pct: float,
        max_positions: int,
    ) -> None:
        self.max_trade_pct = max(0.0, float(max_trade_pct))
        self.risk_per_trade_pct = max(0.0, float(risk_per_trade_pct))
        self.max_symbol_exposure_pct = max(0.0, float(max_symbol_exposure_pct))
        self.max_positions = max(1, int(max_positions))

    @staticmethod
    def _normalize_weights(weights: Mapping[str, float]) -> Dict[str, float]:
        normalized: Dict[str, float] = {}
        total = 0.0
        for name, weight in weights.items():
            w = max(0.0, float(weight))
            if w == 0:
                continue
            normalized[name] = w
            total += w
        if total == 0:
            return {name: 0.0 for name in weights}
        return {name: value / total for name, value in normalized.items()}

    def compute_tradable_equity(
        self,
        *,
        equity: float,
        cap_pct: float,
        reserves: Mapping[str, float],
    ) -> float:
        equity = max(0.0, float(equity))
        cap_pct = max(0.0, min(1.0, float(cap_pct)))
        reserve_total = sum(max(0.0, float(val)) for val in reserves.values())
        reserve_total = min(reserve_total, 0.95)  # keep safety margin
        tradable = equity * cap_pct * (1.0 - reserve_total)
        ops_capital_cap_pct.set(cap_pct * 100.0)
        equity_total_usd.set(equity)
        tradable_equity_usd.set(tradable)
        logger.info(
            "Computed tradable equity equity=%.2f cap_pct=%.2f reserves=%.2f tradable=%.2f",
            equity,
            cap_pct,
            reserve_total,
            tradable,
        )
        return tradable

    def compute_budgets(
        self,
        *,
        equity: float,
        cap_pct: float,
        reserves: Mapping[str, float],
        weights: Mapping[str, float],
    ) -> AllocationResult:
        tradable = self.compute_tradable_equity(
            equity=equity,
            cap_pct=cap_pct,
            reserves=reserves,
        )
        weights_norm = self._normalize_weights(weights)
        per_strategy = {
            name: tradable * weight for name, weight in weights_norm.items()
        }
        for name, budget in per_strategy.items():
            spot_alloc_strategy_usd.labels(strategy=name).set(budget)
        logger.info("Allocated budgets per strategy: %s", per_strategy)
        return AllocationResult(tradable_equity=tradable, per_strategy=per_strategy)

    def risk_size(
        self,
        *,
        equity: float,
        stop_pct: float,
    ) -> float:
        equity = max(0.0, float(equity))
        stop_pct = max(0.0001, float(stop_pct))
        risk_cap = equity * self.risk_per_trade_pct / stop_pct
        notional_cap = equity * self.max_trade_pct
        size = min(risk_cap, notional_cap)
        logger.debug(
            "Risk sizing equity=%.2f stop_pct=%.4f risk_cap=%.2f notional_cap=%.2f size=%.2f",
            equity,
            stop_pct,
            risk_cap,
            notional_cap,
            size,
        )
        return size

    def enforce_limits(
        self,
        *,
        symbol: str,
        notional: float,
        symbol_limits: Mapping[str, float],
    ) -> tuple[bool, str, float]:
        """Adjust notional to satisfy symbol limits.

        Returns a tuple of (ok, reason, adjusted_notional).
        """

        notional = max(0.0, float(notional))
        min_notional = float(symbol_limits.get("min_notional", 0.0))
        lot_size = float(symbol_limits.get("lot_size", 0.0))
        tick_size = float(symbol_limits.get("tick_size", 0.0))
        exposure_limit = float(symbol_limits.get("max_symbol_exposure_pct", self.max_symbol_exposure_pct))

        if notional < min_notional:
            return False, "min_notional", notional

        # Normalize by lot and tick size when available.
        if lot_size > 0:
            steps = max(1, round(notional / lot_size))
            notional = steps * lot_size
        if tick_size > 0:
            price_steps = max(1, round(notional / tick_size))
            notional = price_steps * tick_size

        exposure_pct = symbol_limits.get("current_exposure_pct", 0.0)
        if exposure_pct + (notional / max(symbol_limits.get("equity", notional), 1.0)) > exposure_limit:
            return False, "over_exposure", notional

        return True, "", notional


def compute_total_weight(weights: Iterable[float]) -> float:
    return sum(max(0.0, float(value)) for value in weights)
