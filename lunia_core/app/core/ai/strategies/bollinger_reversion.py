"""Bollinger band reversion strategy."""
from __future__ import annotations

from math import sqrt
from statistics import mean
from typing import Dict, Sequence

from . import StrategySignal, register


def _stdev(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    mu = mean(values)
    variance = sum((x - mu) ** 2 for x in values) / (len(values) - 1)
    return sqrt(max(variance, 0.0))


def generate(symbol: str, prices: Sequence[float], ctx: Dict[str, float]) -> list[StrategySignal]:
    if len(prices) < 20:
        return []
    window = prices[-20:]
    mid = mean(window)
    deviation = _stdev(window)
    if deviation == 0:
        return []
    upper = mid + 2 * deviation
    lower = mid - 2 * deviation
    price = prices[-1]
    side = "BUY" if price <= lower else ("SELL" if price >= upper else "")
    if not side:
        return []
    distance = abs(price - mid) / max(mid, 1.0)
    score = min(distance * 100, 5.0)
    stop_pct = ctx.get("sl_pct_default", 0.15) * 0.85
    take_pct = ctx.get("tp_pct_default", 0.30) * 1.1
    return [
        StrategySignal(
            symbol=symbol,
            side=side,
            score=score,
            price=price,
            stop_pct=stop_pct,
            take_pct=take_pct,
            strategy="bollinger_reversion",
            meta={"mid": mid, "band_width": deviation},
        )
    ]


register("bollinger_reversion", generate)
