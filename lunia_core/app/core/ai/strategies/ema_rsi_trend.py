"""EMA plus RSI trend confirmation strategy."""
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


def _rsi(prices: Sequence[float], period: int = 14) -> float:
    if len(prices) < period + 1:
        return 50.0
    gains = 0.0
    losses = 0.0
    for idx in range(-period, 0):
        delta = prices[idx] - prices[idx - 1]
        if delta > 0:
            gains += delta
        else:
            losses += abs(delta)
    if losses == 0:
        return 100.0
    if gains == 0:
        return 0.0
    rs = gains / losses
    return 100 - (100 / (1 + rs))


def generate(symbol: str, prices: Sequence[float], ctx: Dict[str, float]) -> list[StrategySignal]:
    if len(prices) < 30:
        return []
    price = prices[-1]
    ema_fast = _ema(prices[-20:], 9)
    ema_slow = _ema(prices[-30:], 21)
    rsi = _rsi(prices[-20:])
    if ema_fast > ema_slow and rsi > 55:
        side = "BUY"
        score = min((rsi - 50) / 10, 5.0)
    elif ema_fast < ema_slow and rsi < 45:
        side = "SELL"
        score = min((50 - rsi) / 10, 5.0)
    else:
        return []
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
            strategy="ema_rsi_trend",
            meta={"ema_fast": ema_fast, "ema_slow": ema_slow, "rsi": rsi},
        )
    ]


register("ema_rsi_trend", generate)
