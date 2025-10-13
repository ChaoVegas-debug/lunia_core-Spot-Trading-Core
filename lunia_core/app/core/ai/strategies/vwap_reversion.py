"""VWAP reversion strategy."""
from __future__ import annotations

from typing import Dict, Sequence

from . import StrategySignal, register


def generate(symbol: str, prices: Sequence[float], ctx: Dict[str, float]) -> list[StrategySignal]:
    if len(prices) < 15:
        return []
    price = prices[-1]
    weights = list(range(1, len(prices[-15:]) + 1))
    weighted_sum = sum(p * w for p, w in zip(prices[-15:], weights))
    vwap = weighted_sum / sum(weights)
    deviation = (price - vwap) / max(vwap, 1.0)
    if abs(deviation) < 0.002:
        return []
    side = "BUY" if deviation < 0 else "SELL"
    score = min(abs(deviation) * 200, 5.0)
    stop_pct = ctx.get("sl_pct_default", 0.15)
    take_pct = ctx.get("tp_pct_default", 0.30) * 0.9
    return [
        StrategySignal(
            symbol=symbol,
            side=side,
            score=score,
            price=price,
            stop_pct=stop_pct,
            take_pct=take_pct,
            strategy="vwap_reversion",
            meta={"vwap": vwap, "deviation": deviation},
        )
    ]


register("vwap_reversion", generate)
