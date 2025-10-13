from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict, Tuple

from app.core.metrics import arb_rate_limited_total


@dataclass
class RateLimitConfig:
    enabled: bool = os.getenv("ARB_RATE_LIMIT_ENABLED", "true").lower() == "true"
    window_minutes: int = int(os.getenv("ARB_RATE_LIMIT_WINDOW_MIN", "10"))
    max_per_exchange: int = int(os.getenv("ARB_RATE_LIMIT_MAX_EXEC_PER_EXCHANGE", "3"))
    max_per_symbol: int = int(os.getenv("ARB_RATE_LIMIT_MAX_EXEC_PER_SYMBOL", "5"))

    def window_seconds(self) -> int:
        return max(60, self.window_minutes * 60)


class RateLimiter:
    """Simple in-memory rate limiter for arbitrage executions."""

    def __init__(self, config: RateLimitConfig | None = None) -> None:
        self.config = config or RateLimitConfig()
        self._per_exchange: Dict[str, Deque[float]] = defaultdict(deque)
        self._per_symbol: Dict[str, Deque[float]] = defaultdict(deque)

    def _prune(self, queue: Deque[float], now: float) -> None:
        window = self.config.window_seconds()
        while queue and now - queue[0] > window:
            queue.popleft()

    def allow(self, buy_exchange: str, sell_exchange: str, symbol: str) -> Tuple[bool, str]:
        if not self.config.enabled:
            return True, ""
        now = time.time()
        for key in (buy_exchange, sell_exchange):
            q = self._per_exchange[key]
            self._prune(q, now)
            if len(q) >= self.config.max_per_exchange:
                arb_rate_limited_total.labels(reason="exchange").inc()
                return False, f"rate limit exchange {key}"
        q_symbol = self._per_symbol[symbol]
        self._prune(q_symbol, now)
        if len(q_symbol) >= self.config.max_per_symbol:
            arb_rate_limited_total.labels(reason="symbol").inc()
            return False, f"rate limit symbol {symbol}"
        return True, ""

    def record(self, buy_exchange: str, sell_exchange: str, symbol: str) -> None:
        if not self.config.enabled:
            return
        now = time.time()
        for key in (buy_exchange, sell_exchange):
            q = self._per_exchange[key]
            q.append(now)
        self._per_symbol[symbol].append(now)


__all__ = ["RateLimiter", "RateLimitConfig"]
