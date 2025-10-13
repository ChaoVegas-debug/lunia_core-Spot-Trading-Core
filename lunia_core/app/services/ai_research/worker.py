"""AI research worker providing on-demand analysis."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from ...core.bus import get_bus
from ...core.metrics import (
    ai_priority_signal_total,
    ai_research_confidence_avg,
    ai_research_runs_total,
    ai_research_signal_total,
)
from ...core.state import get_state
from .collector import collect_market_data
from .client import synthesize_research

LOG_DIR = Path(__file__).resolve().parents[4] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = LOG_DIR / "ai_research.log"

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

_DEFAULT_STRATEGIES = [
    "scalping_breakout",
    "micro_trend_scalper",
    "liquidity_snipe",
]


_PRIORITY: Dict[str, float] = {}


def _choose_strategy(index: int) -> str:
    return _DEFAULT_STRATEGIES[index % len(_DEFAULT_STRATEGIES)]


def _derive_bias(symbol: str, idx: int) -> str:
    return ["LONG", "SHORT", "FLAT"][idx % 3]


def _confidence(idx: int) -> float:
    return 0.55 + (idx % 3) * 0.1


def run_research_now(pairs: Optional[Iterable[str]] = None, mode: str = "manual") -> List[Dict[str, object]]:
    """Execute a single research run and publish results."""
    runtime = get_state()
    if runtime.get("global_stop") and mode != "manual":
        logger.info("Global stop active; research skipped")
        return []
    if pairs is None:
        env_pairs = os.getenv("AI_RESEARCH_PAIRS", "BTCUSDT")
        pairs = [token.strip() for token in env_pairs.split(",") if token.strip()]
    pairs = list(pairs)
    market_data = collect_market_data(pairs)
    bus = get_bus()
    results: List[Dict[str, object]] = []

    for idx, data in enumerate(market_data):
        symbol = data["symbol"]
        bias = _derive_bias(symbol, idx)
        strategy = _choose_strategy(idx)
        confidence = _confidence(idx)
        summary = synthesize_research([data], strategy)
        result = {
            "pair": symbol,
            "bias": bias,
            "confidence": round(confidence, 2),
            "suggested_strategy": strategy,
            "comment": summary,
            "features": data,
        }
        results.append(result)
        ai_research_signal_total.labels(strategy=strategy, bias=bias).inc()
        ai_priority_signal_total.labels(pair=symbol, bias=bias).inc()
        _PRIORITY[symbol] = confidence
        if bus:
            try:
                bus.publish("ai.research.signal", result)
            except Exception as exc:  # pragma: no cover - bus failures
                logger.warning("Failed to publish research result: %s", exc)

    if results:
        avg_conf = sum(item["confidence"] for item in results) / len(results)
        ai_research_confidence_avg.set(avg_conf)
    ai_research_runs_total.labels(mode=mode).inc()
    logger.info("Research run completed mode=%s pairs=%s", mode, pairs)
    return results


def get_priority_scores() -> Dict[str, float]:
    return dict(_PRIORITY)
