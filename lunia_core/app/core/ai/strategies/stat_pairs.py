"""Simple statistical pairs strategy within USDC universe."""
from __future__ import annotations

from typing import Dict, Sequence

from . import StrategySignal, register


PAIR_REL = {
    "BTCUSDT": "ETHUSDT",
    "ETHUSDT": "BTCUSDT",
    "SOLUSDT": "BNBUSDT",
}


def generate(symbol: str, prices: Sequence[float], ctx: Dict[str, float]) -> list[StrategySignal]:
    ref_symbol = PAIR_REL.get(symbol)
    ref_series = ctx.get("reference_prices", {}).get(ref_symbol)
    if not ref_series or len(prices) < 10 or len(ref_series) < 10:
        return []
    price_ratio = prices[-1] / max(ref_series[-1], 1e-6)
    average_ratio = sum(p / max(r, 1e-6) for p, r in zip(prices[-10:], ref_series[-10:])) / 10
    deviation = (price_ratio - average_ratio) / max(average_ratio, 1e-6)
    if abs(deviation) < 0.01:
        return []
    side = "SELL" if deviation > 0 else "BUY"
    score = min(abs(deviation) * 50, 5.0)
    stop_pct = ctx.get("sl_pct_default", 0.15)
    take_pct = ctx.get("tp_pct_default", 0.30)
    return [
        StrategySignal(
            symbol=symbol,
            side=side,
            score=score,
            price=prices[-1],
            stop_pct=stop_pct,
            take_pct=take_pct,
            strategy="stat_pairs",
            meta={"ratio": price_ratio, "avg_ratio": average_ratio},
        )
    ]


register("stat_pairs", generate)
