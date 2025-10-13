"""Scalping breakout strategy with adaptive targets."""
from __future__ import annotations

from statistics import mean
from typing import Dict, Sequence

from . import StrategySignal, register


def generate(symbol: str, prices: Sequence[float], ctx: Dict[str, float]) -> list[StrategySignal]:
    if len(prices) < 10:
        return []
    price = prices[-1]
    window = prices[-10:]
    high = max(window)
    low = min(window)
    range_pct = (high - low) / max(low, 1.0)
    if range_pct < 0.001:
        return []
    mean_price = mean(window)
    side = "BUY" if price >= high else ("SELL" if price <= low else "")
    if not side:
        return []
    stop_pct = ctx.get("sl_pct_default", 0.15)
    take_pct = ctx.get("tp_pct_default", 0.30)
    adaptive_factor = min(range_pct * 100, 5.0)
    if side == "BUY":
        take_pct *= 1 + adaptive_factor / 10
        stop_pct *= 0.8
    else:
        take_pct *= 1 + adaptive_factor / 8
        stop_pct *= 0.9
    score = adaptive_factor
    return [
        StrategySignal(
            symbol=symbol,
            side=side,
            score=score,
            price=price,
            stop_pct=stop_pct,
            take_pct=take_pct,
            strategy="scalping_breakout",
            meta={"range_pct": range_pct, "mean": mean_price},
        )
    ]


register("scalping_breakout", generate)
