"""Micro trend scalper strategy implementation."""
from __future__ import annotations

from statistics import mean
from typing import Dict, Sequence

from . import StrategySignal, register


def _momentum(prices: Sequence[float]) -> float:
    if len(prices) < 3:
        return 0.0
    return prices[-1] - prices[-3]


def generate(symbol: str, prices: Sequence[float], ctx: Dict[str, float]) -> list[StrategySignal]:
    if len(prices) < 5:
        return []
    momentum = _momentum(prices)
    if momentum == 0:
        return []
    side = "BUY" if momentum > 0 else "SELL"
    price = prices[-1]
    base_score = abs(momentum) / max(mean(prices[-5:]), 1.0) * 100
    score = min(base_score, 5.0)
    stop_pct = ctx.get("sl_pct_default", 0.15) * 0.9
    take_pct = ctx.get("tp_pct_default", 0.30) * 0.8
    return [
        StrategySignal(
            symbol=symbol,
            side=side,
            score=score,
            price=price,
            stop_pct=stop_pct,
            take_pct=take_pct,
            strategy="micro_trend_scalper",
            meta={"momentum": momentum},
        )
    ]


register("micro_trend_scalper", generate)
