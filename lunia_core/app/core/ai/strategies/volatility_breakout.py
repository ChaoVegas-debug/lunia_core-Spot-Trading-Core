"""Volatility breakout strategy."""
from __future__ import annotations

from statistics import pstdev
from typing import Dict, Sequence

from . import StrategySignal, register


def generate(symbol: str, prices: Sequence[float], ctx: Dict[str, float]) -> list[StrategySignal]:
    if len(prices) < 25:
        return []
    window = prices[-25:]
    price = window[-1]
    vol = pstdev(window)
    if vol == 0:
        return []
    threshold = vol * 1.5
    move = price - window[-2]
    if abs(move) < threshold:
        return []
    side = "BUY" if move > 0 else "SELL"
    score = min(abs(move) / max(threshold, 1e-6), 5.0)
    stop_pct = ctx.get("sl_pct_default", 0.15)
    take_pct = ctx.get("tp_pct_default", 0.30) * 1.2
    return [
        StrategySignal(
            symbol=symbol,
            side=side,
            score=score,
            price=price,
            stop_pct=stop_pct,
            take_pct=take_pct,
            strategy="volatility_breakout",
            meta={"vol": vol, "move": move},
        )
    ]


register("volatility_breakout", generate)
