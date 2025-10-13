"""Lightweight grid strategy without martingale."""
from __future__ import annotations

from typing import Dict, Sequence

from . import StrategySignal, register


def generate(symbol: str, prices: Sequence[float], ctx: Dict[str, float]) -> list[StrategySignal]:
    if len(prices) < 12:
        return []
    price = prices[-1]
    median = sorted(prices[-12:])[len(prices[-12:]) // 2]
    deviation = (price - median) / max(median, 1.0)
    if abs(deviation) < 0.001:
        return []
    side = "SELL" if deviation > 0 else "BUY"
    grid_step = ctx.get("grid_step_pct", 0.25)
    take_pct = grid_step
    stop_pct = grid_step * 0.8
    score = min(abs(deviation) * 100, 3.0)
    return [
        StrategySignal(
            symbol=symbol,
            side=side,
            score=score,
            price=price,
            stop_pct=stop_pct,
            take_pct=take_pct,
            strategy="grid_light",
            meta={"deviation": deviation, "grid_step": grid_step},
        )
    ]


register("grid_light", generate)
