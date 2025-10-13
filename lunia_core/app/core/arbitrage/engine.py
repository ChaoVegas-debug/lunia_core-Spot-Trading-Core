"""Arbitrage opportunity scanning engine."""
from __future__ import annotations

import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Deque, Dict, Iterable, List, Optional, Sequence

from ..exchange.base import IExchange
from ..exchange.binance_spot import BinanceSpot
from ..exchange.bybit_spot import BybitSpot
from ..exchange.okx_spot import OKXSpot
from ..metrics import (
    arbitrage_avg_spread_pct,
    arbitrage_opportunities_total,
    arbitrage_scan_latency_ms,
)

LOG_PATH = Path(__file__).resolve().parents[4] / "logs" / "arbitrage.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

CONFIG_PATH = Path(__file__).with_name("config.yaml")


@dataclass
class ArbitragePair:
    symbol: str
    exchanges: Sequence[str]


@dataclass
class ArbitrageConfig:
    pairs: List[ArbitragePair] = field(default_factory=list)
    spread_threshold_pct: float = 0.25
    qty_usd: float = 100.0
    execution_mode: str = "simulation"
    scan_interval_sec: int = 3

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "ArbitrageConfig":
        pairs_payload = payload.get("pairs", [])
        pairs: List[ArbitragePair] = []
        for entry in pairs_payload or []:
            if not isinstance(entry, dict):
                continue
            symbol = str(entry.get("symbol", "BTCUSDT"))
            exchanges = entry.get("exchanges", [])
            if not isinstance(exchanges, Iterable):
                exchanges = []
            pairs.append(ArbitragePair(symbol=symbol, exchanges=list(exchanges)))
        return cls(
            pairs=pairs,
            spread_threshold_pct=float(payload.get("spread_threshold_pct", 0.25)),
            qty_usd=float(payload.get("qty_usd", 100.0)),
            execution_mode=str(payload.get("execution_mode", "simulation")),
            scan_interval_sec=int(payload.get("scan_interval_sec", 3)),
        )


@dataclass
class ArbitrageOpportunity:
    symbol: str
    buy_ex: str
    sell_ex: str
    buy_px: float
    sell_px: float
    spread_pct: float
    timestamp: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "symbol": self.symbol,
            "buy_ex": self.buy_ex,
            "sell_ex": self.sell_ex,
            "buy_px": self.buy_px,
            "sell_px": self.sell_px,
            "spread_pct": self.spread_pct,
            "ts": self.timestamp,
        }


def _parse_simple_yaml(text: str) -> Dict[str, object]:
    """Parse a limited subset of YAML for offline environments."""

    def parse_value(raw: str) -> object:
        raw = raw.strip()
        if not raw:
            return ""
        if raw.startswith("[") and raw.endswith("]"):
            inner = raw[1:-1].strip()
            if not inner:
                return []
            return [part.strip().strip("\"") for part in inner.split(",")]
        if raw.startswith("\"") and raw.endswith("\""):
            return raw[1:-1]
        lowered = raw.lower()
        if lowered in {"true", "false"}:
            return lowered == "true"
        try:
            if "." in raw:
                return float(raw)
            return int(raw)
        except ValueError:
            return raw

    result: Dict[str, object] = {}
    current_key: Optional[str] = None
    current_list: Optional[List[Dict[str, object]]] = None
    current_item: Optional[Dict[str, object]] = None

    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.strip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()

        if indent == 0 and not stripped.startswith("-"):
            if current_item is not None and current_list is not None:
                current_list.append(current_item)
                current_item = None
            current_list = None
            if ":" in stripped:
                key, value = stripped.split(":", 1)
                key = key.strip()
                value = value.strip()
                if value == "":
                    current_key = key
                    current_list = []
                    result[key] = current_list
                else:
                    result[key] = parse_value(value)
            continue

        if stripped.startswith("-"):
            if current_list is None:
                current_list = []
                if current_key:
                    result[current_key] = current_list
            if current_item is not None:
                current_list.append(current_item)
            current_item = {}
            remainder = stripped[1:].strip()
            if remainder and ":" in remainder:
                k, v = remainder.split(":", 1)
                current_item[k.strip()] = parse_value(v.strip())
            continue

        if current_item is not None and ":" in stripped:
            k, v = stripped.split(":", 1)
            current_item[k.strip()] = parse_value(v.strip())

    if current_item is not None and current_list is not None:
        current_list.append(current_item)

    return result


def load_config(path: Path = CONFIG_PATH) -> ArbitrageConfig:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        payload = yaml.safe_load(text) or {}
    except Exception:
        payload = _parse_simple_yaml(text)
    return ArbitrageConfig.from_dict(payload)


class ArbitrageEngine:
    """Engine scanning configured exchanges for arbitrage spreads."""

    def __init__(
        self,
        clients: Optional[Dict[str, IExchange]] = None,
        config: Optional[ArbitrageConfig] = None,
        config_path: Path = CONFIG_PATH,
    ) -> None:
        self.config = config or load_config(config_path)
        self.clients = clients or self._default_clients()
        self.last_scan_ts: float = 0.0
        self.last_latency_ms: float = 0.0
        self.total_opportunities: int = 0
        self.recent: Deque[ArbitrageOpportunity] = deque(maxlen=50)

    def _default_clients(self) -> Dict[str, IExchange]:
        use_testnet = os.getenv("BINANCE_USE_TESTNET", "true").lower() == "true"
        api_key = os.getenv("BINANCE_API_KEY")
        api_secret = os.getenv("BINANCE_API_SECRET")
        return {
            "binance": BinanceSpot(
                api_key=api_key,
                api_secret=api_secret,
                use_testnet=use_testnet,
                mock=not use_testnet,
            ),
            "okx": OKXSpot(),
            "bybit": BybitSpot(),
        }

    def _get_price(self, exchange: str, symbol: str) -> Optional[float]:
        client = self.clients.get(exchange)
        if client is None:
            logger.warning("No client configured for exchange %s", exchange)
            return None
        try:
            price = float(client.get_price(symbol))
            return price
        except Exception as exc:  # pragma: no cover - external failure path
            logger.warning("Failed to fetch price from %s for %s: %s", exchange, symbol, exc)
            return None

    def scan(self) -> List[ArbitrageOpportunity]:
        start = time.perf_counter()
        opportunities: List[ArbitrageOpportunity] = []

        for pair in self.config.pairs:
            prices: Dict[str, float] = {}
            for exchange in pair.exchanges:
                price = self._get_price(exchange, pair.symbol)
                if price is None:
                    continue
                prices[exchange] = price
            if len(prices) < 2:
                continue

            buy_ex = min(prices, key=prices.get)
            sell_ex = max(prices, key=prices.get)
            buy_px = prices[buy_ex]
            sell_px = prices[sell_ex]
            if buy_px <= 0:
                continue
            spread_pct = ((sell_px - buy_px) / buy_px) * 100
            logger.debug(
                "Pair %s buy %s %.2f sell %s %.2f spread=%.4f%%",
                pair.symbol,
                buy_ex,
                buy_px,
                sell_ex,
                sell_px,
                spread_pct,
            )
            if spread_pct >= self.config.spread_threshold_pct:
                opportunity = ArbitrageOpportunity(
                    symbol=pair.symbol,
                    buy_ex=buy_ex,
                    sell_ex=sell_ex,
                    buy_px=buy_px,
                    sell_px=sell_px,
                    spread_pct=spread_pct,
                    timestamp=time.time(),
                )
                opportunities.append(opportunity)
                self.recent.append(opportunity)
                self.total_opportunities += 1
                arbitrage_opportunities_total.labels(symbol=pair.symbol, buy=buy_ex, sell=sell_ex).inc()
                logger.info("Arbitrage opportunity found: %s", opportunity)

        latency_ms = (time.perf_counter() - start) * 1000
        self.last_latency_ms = latency_ms
        self.last_scan_ts = time.time()
        arbitrage_scan_latency_ms.observe(latency_ms)

        if opportunities:
            avg_spread = sum(opp.spread_pct for opp in opportunities) / len(opportunities)
            arbitrage_avg_spread_pct.set(avg_spread)
        else:
            arbitrage_avg_spread_pct.set(0.0)

        return opportunities

    def get_recent(self, limit: int = 20) -> List[Dict[str, object]]:
        limit = max(1, min(limit, len(self.recent)))
        return [opp.to_dict() for opp in list(self.recent)[-limit:]]
