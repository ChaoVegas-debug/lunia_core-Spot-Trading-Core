"""Liquidity snipe strategy producing aggressive/safe variants."""
from __future__ import annotations

from typing import Dict, Sequence

from . import StrategySignal, register


def generate(symbol: str, prices: Sequence[float], ctx: Dict[str, float]) -> list[StrategySignal]:
    if len(prices) < 5:
        return []
    price = prices[-1]
    depth_ratio = ctx.get("orderbook_depth_ratio", 0.5)
    volatility = ctx.get("volatility", 0.01)
    side = "BUY" if depth_ratio > 0.5 else "SELL"
    base_score = min(max(volatility * 100, 0.1), 5.0)
    safe_stop = ctx.get("sl_pct_default", 0.15) * 1.1
    safe_take = ctx.get("tp_pct_default", 0.30) * 0.9
    aggressive_stop = safe_stop * 0.6
    aggressive_take = safe_take * 1.3
    return [
        StrategySignal(
            symbol=symbol,
            side=side,
            score=base_score,
            price=price,
            stop_pct=safe_stop,
            take_pct=safe_take,
            strategy="liquidity_snipe_safe",
            meta={"variant": "safe", "depth_ratio": depth_ratio},
        ),
        StrategySignal(
            symbol=symbol,
            side=side,
            score=base_score * 1.2,
            price=price,
            stop_pct=aggressive_stop,
            take_pct=aggressive_take,
            strategy="liquidity_snipe_aggressive",
            meta={"variant": "aggressive", "depth_ratio": depth_ratio},
        ),
    ]


register("liquidity_snipe", generate)
