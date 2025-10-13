"""MACD crossover strategy."""
from __future__ import annotations

from typing import Dict, Sequence

from . import StrategySignal, register


def _ema(prices: Sequence[float], period: int) -> float:
    if not prices:
        return 0.0
    multiplier = 2 / (period + 1)
    ema = prices[0]
    for price in prices[1:]:
        ema = (price - ema) * multiplier + ema
    return ema


def generate(symbol: str, prices: Sequence[float], ctx: Dict[str, float]) -> list[StrategySignal]:
    if len(prices) < 26:
        return []
    fast = _ema(prices[-26:], 12)
    slow = _ema(prices[-26:], 26)
    signal_line = _ema([fast - slow for _ in range(9)], 9)
    macd_value = fast - slow
    histogram = macd_value - signal_line
    if abs(histogram) < 0.0001:
        return []
    side = "BUY" if histogram > 0 else "SELL"
    price = prices[-1]
    score = min(abs(histogram) * 1000, 5.0)
    stop_pct = ctx.get("sl_pct_default", 0.15)
    take_pct = ctx.get("tp_pct_default", 0.30)
    return [
        StrategySignal(
            symbol=symbol,
            side=side,
            score=score,
            price=price,
            stop_pct=stop_pct,
            take_pct=take_pct,
            strategy="macd_crossover",
            meta={"macd": macd_value, "hist": histogram},
        )
    ]


register("macd_crossover", generate)
