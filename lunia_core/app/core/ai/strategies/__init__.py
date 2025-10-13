"""Strategy registry for spot trading."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Sequence


@dataclass
class StrategySignal:
    symbol: str
    side: str
    score: float
    price: float
    stop_pct: float
    take_pct: float
    strategy: str
    meta: Dict[str, float]


StrategyFunc = Callable[[str, Sequence[float], Dict[str, float]], List[StrategySignal]]

REGISTRY: Dict[str, StrategyFunc] = {}


def register(name: str, func: StrategyFunc) -> None:
    REGISTRY[name] = func


def strategies() -> Iterable[str]:
    return REGISTRY.keys()


from . import (  # noqa: E402,F401  (register on import)
    bollinger_reversion,
    ema_rsi_trend,
    grid_light,
    liquidity_snipe,
    macd_crossover,
    micro_trend_scalper,
    scalping_breakout,
    stat_pairs,
    volatility_breakout,
    vwap_reversion,
)

__all__ = ["StrategySignal", "StrategyFunc", "REGISTRY", "register", "strategies"]
