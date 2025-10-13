"""Market data collector for AI research (placeholder implementation)."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, List


def collect_market_data(pairs: Iterable[str]) -> List[Dict[str, object]]:
    """Return deterministic placeholder metrics for each pair."""
    payload: List[Dict[str, object]] = []
    for symbol in pairs:
        symbol = symbol.upper()
        payload.append(
            {
                "symbol": symbol,
                "timestamp": datetime.utcnow().isoformat(),
                "funding_rate": 0.0001,
                "open_interest_change": 1.2,
                "whale_ratio": 0.45,
                "news_sentiment": 0.1,
            }
        )
    return payload
