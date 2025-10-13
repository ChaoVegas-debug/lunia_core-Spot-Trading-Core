"""Enhanced arbitrage opportunity scanner with filtering and metrics."""
from __future__ import annotations

import itertools
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence

from app.core.metrics import (
    arb_filtered_out_total,
    arb_net_profit_usd_bucket,
    arb_net_roi_pct_bucket,
    arb_proposals_after_filter_total,
    arb_proposals_total,
    arb_qty_suggested_usd,
    arb_scans_total,
)
from app.core.state import get_state

try:  # pragma: no cover - optional integration
    from app.services.ai_research.worker import get_priority_scores
except Exception:  # pragma: no cover - offline fallback

    def get_priority_scores() -> Dict[str, float]:
        return {}
from app.db.reporting import record_arbitrage_proposal

logger = logging.getLogger(__name__)


@dataclass
class ArbitrageFilters:
    """Runtime filters that control which opportunities survive."""

    min_net_roi_pct: float = 0.0
    max_net_roi_pct: float = 100.0
    min_net_usd: float = 0.0
    top_k: int = 5
    sort_key: str = "net_roi_pct"
    sort_dir: str = "desc"


@dataclass
class ArbitrageOpportunity:
    """Snapshot of a potential arbitrage trade."""

    proposal_id: str
    symbol: str
    buy_exchange: str
    sell_exchange: str
    buy_price: float
    sell_price: float
    gross_spread_pct: float
    fees_total_pct: float
    slippage_est_pct: float
    net_roi_pct: float
    net_profit_usd: float
    qty_usd: float
    created_at: float
    transfer_type: str
    latency_ms: float
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "id": self.proposal_id,
            "symbol": self.symbol,
            "buy_exchange": self.buy_exchange,
            "sell_exchange": self.sell_exchange,
            "buy_price": round(self.buy_price, 8),
            "sell_price": round(self.sell_price, 8),
            "gross_spread_pct": round(self.gross_spread_pct, 6),
            "fees_total_pct": round(self.fees_total_pct, 6),
            "slippage_est_pct": round(self.slippage_est_pct, 6),
            "net_roi_pct": round(self.net_roi_pct, 6),
            "net_profit_usd": round(self.net_profit_usd, 6),
            "qty_usd": round(self.qty_usd, 2),
            "created_at": self.created_at,
            "transfer_type": self.transfer_type,
            "latency_ms": self.latency_ms,
            "meta": self.meta,
        }
        return payload


class ArbitrageScanner:
    """Scanner that evaluates spreads across multiple exchanges."""

    def __init__(
        self,
        exchanges: Mapping[str, Any],
        symbols: Sequence[str],
        qty_usd: float,
        limits_path: Optional[Path] = None,
    ) -> None:
        self._exchanges = dict(exchanges)
        self._symbols = list(symbols)
        self._qty_usd = float(qty_usd)
        self._priority_cache: Dict[str, float] = {}
        self._limits = self._load_limits(limits_path)
        self._last_result: List[ArbitrageOpportunity] = []
        self._last_filters: ArbitrageFilters | None = None
        self._last_ts: float = 0.0

    @property
    def last_opportunities(self) -> List[ArbitrageOpportunity]:
        return list(self._last_result)

    @property
    def last_filters(self) -> ArbitrageFilters | None:
        return self._last_filters

    @property
    def last_timestamp(self) -> float:
        return self._last_ts

    def scan(self, filters: ArbitrageFilters) -> List[ArbitrageOpportunity]:
        """Run a scan over all symbols/exchanges applying runtime filters."""

        arb_scans_total.inc()
        start = time.time()
        self._priority_cache = get_priority_scores()
        raw: List[ArbitrageOpportunity] = []
        for symbol in self._symbols:
            for buy, sell in itertools.permutations(self._exchanges.keys(), 2):
                opportunity = self._evaluate(symbol, buy, sell)
                if opportunity is None:
                    continue
                raw.append(opportunity)
                arb_proposals_total.inc()
        filtered = self._apply_filters(raw, filters)
        if filters.sort_key == "net_profit_usd":
            key_func = lambda opp: opp.net_profit_usd
        else:
            key_func = lambda opp: opp.net_roi_pct
        reverse = filters.sort_dir.lower() != "asc"
        filtered.sort(key=key_func, reverse=reverse)
        top_limit = max(1, filters.top_k)
        top_filtered = filtered[:top_limit]
        self._last_result = list(top_filtered)
        self._last_filters = filters
        self._last_ts = time.time()
        latency_ms = (self._last_ts - start) * 1000
        logger.info(
            "arbitrage scan completed opportunities=%s filtered=%s latency_ms=%.2f",
            len(raw),
            len(top_filtered),
            latency_ms,
        )
        return list(top_filtered)

    def _evaluate(self, symbol: str, buy: str, sell: str) -> ArbitrageOpportunity | None:
        buy_client = self._exchanges.get(buy)
        sell_client = self._exchanges.get(sell)
        if buy_client is None or sell_client is None:
            return None
        try:
            buy_price = float(buy_client.get_price(symbol))
            sell_price = float(sell_client.get_price(symbol))
        except Exception as exc:  # pragma: no cover - network failure fallback
            logger.warning("price lookup failed symbol=%s buy=%s sell=%s err=%s", symbol, buy, sell, exc)
            return None
        if buy_price <= 0 or sell_price <= 0:
            return None
        limits = self._limits.get("exchanges", {})
        buy_limits = limits.get(buy, {})
        sell_limits = limits.get(sell, {})
        symbol_limits = self._limits.get("symbols", {}).get(symbol, {})
        spread_bps_buy = float(buy_limits.get("spread_bps", symbol_limits.get("spread_bps", 5.0)))
        spread_bps_sell = float(sell_limits.get("spread_bps", symbol_limits.get("spread_bps", 5.0)))
        ask_price = buy_price * (1 + spread_bps_buy / 10000)
        bid_price = sell_price * (1 - spread_bps_sell / 10000)
        gross_spread_pct = ((bid_price - ask_price) / ask_price) * 100
        taker_buy = float(buy_limits.get("taker_fee_pct", 0.1))
        taker_sell = float(sell_limits.get("taker_fee_pct", 0.1))
        withdraw_fee_usd = float(buy_limits.get("withdraw_fee_usd", 0.0))
        deposit_fee_usd = float(sell_limits.get("deposit_fee_usd", 0.0))
        transfer_type = "internal" if buy_limits.get("internal_transfer") and sell_limits.get("internal_transfer") else "chain"
        transfer_fee_usd = withdraw_fee_usd + deposit_fee_usd
        transfer_eta = float(self._limits.get("transfer_eta_sec", {}).get(transfer_type, 60.0))
        if transfer_type == "internal":
            transfer_fee_usd = float(self._limits.get("transfer_internal_fee_usd", 0.0))
        depth_buy = float(buy_limits.get("depth_usd", symbol_limits.get("depth_usd", 100000.0)))
        depth_sell = float(sell_limits.get("depth_usd", symbol_limits.get("depth_usd", 100000.0)))
        qty_usd = self._suggest_qty_usd(symbol, buy_limits, sell_limits, symbol_limits, depth_buy, depth_sell)
        fees_total_pct = taker_buy + taker_sell + (transfer_fee_usd / qty_usd * 100 if qty_usd else 0.0)
        slippage_factor = float(self._limits.get("slippage_factor", 1.0))
        depth = max(depth_buy, 1.0)
        rel = min(qty_usd / depth, 1.0)
        slippage_est_pct = rel * slippage_factor
        priority = self._priority_weight(symbol)
        net_roi_pct = gross_spread_pct - fees_total_pct - slippage_est_pct
        if priority:
            net_roi_pct = net_roi_pct * (1 + priority)
        net_profit_usd = qty_usd * (net_roi_pct / 100)
        proposal_id = f"{symbol}:{buy}->{sell}:{int(time.time()*1000)}"
        latency_ms = float(max(buy_limits.get("latency_ms", 200.0), sell_limits.get("latency_ms", 200.0)))
        meta = {
            "fees": {
                "taker_buy_pct": taker_buy,
                "taker_sell_pct": taker_sell,
                "transfer_fee_usd": transfer_fee_usd,
            },
            "slippage": {
                "depth_buy_usd": depth_buy,
                "depth_sell_usd": depth_sell,
                "est_pct": slippage_est_pct,
            },
            "transfer": {
                "type": transfer_type,
                "eta_sec": transfer_eta,
            },
            "qty": {
                "suggested_usd": qty_usd,
                "base_usd": self._qty_usd,
                "priority_weight": priority,
            },
            "raw_prices": {
                "ask": ask_price,
                "bid": bid_price,
            },
        }
        opportunity = ArbitrageOpportunity(
            proposal_id=proposal_id,
            symbol=symbol,
            buy_exchange=buy,
            sell_exchange=sell,
            buy_price=ask_price,
            sell_price=bid_price,
            gross_spread_pct=gross_spread_pct,
            fees_total_pct=fees_total_pct,
            slippage_est_pct=slippage_est_pct,
            net_roi_pct=net_roi_pct,
            net_profit_usd=net_profit_usd,
            qty_usd=qty_usd,
            created_at=time.time(),
            transfer_type=transfer_type,
            latency_ms=latency_ms,
            meta=meta,
        )
        return opportunity

    def _priority_weight(self, symbol: str) -> float:
        if not self._priority_cache:
            self._priority_cache = get_priority_scores()
        score = self._priority_cache.get(symbol)
        if score is None:
            return 0.0
        # map confidence 0..1 to up to +25% weighting
        return max(score - 0.5, 0.0) * 0.5

    def _suggest_qty_usd(
        self,
        symbol: str,
        buy_limits: Mapping[str, Any],
        sell_limits: Mapping[str, Any],
        symbol_limits: Mapping[str, Any],
        depth_buy: float,
        depth_sell: float,
    ) -> float:
        state = get_state()
        arb_state = state.get("arb", {})
        base_qty = float(arb_state.get("qty_usd", self._qty_usd))
        min_qty = float(arb_state.get("qty_min_usd", base_qty))
        max_qty = float(arb_state.get("qty_max_usd", max(base_qty, min_qty)))
        min_qty = max(min_qty, 1.0)
        max_qty = max(max_qty, min_qty)
        available_buy = float(buy_limits.get("available_usd", depth_buy))
        available_sell = float(sell_limits.get("available_usd", depth_sell))
        liquidity_cap = max(min(available_buy, available_sell, depth_buy, depth_sell) * 0.25, min_qty)
        volatility = float(symbol_limits.get("volatility_pct", 1.0))
        volatility = max(volatility, 0.1)
        adjusted = base_qty / (1 + volatility)
        suggested = min(max_qty, max(min_qty, min(liquidity_cap, adjusted)))
        arb_qty_suggested_usd.observe(max(suggested, 0.0))
        return suggested

    def _apply_filters(
        self, opportunities: Sequence[ArbitrageOpportunity], filters: ArbitrageFilters
    ) -> List[ArbitrageOpportunity]:
        filtered: List[ArbitrageOpportunity] = []
        for opportunity in opportunities:
            if opportunity.net_roi_pct < filters.min_net_roi_pct:
                arb_filtered_out_total.labels(reason="roi_low").inc()
                record_arbitrage_proposal(opportunity, filtered_out=True, reason="roi_low")
                continue
            if opportunity.net_roi_pct > filters.max_net_roi_pct:
                arb_filtered_out_total.labels(reason="roi_high").inc()
                record_arbitrage_proposal(opportunity, filtered_out=True, reason="roi_high")
                continue
            if opportunity.net_profit_usd < filters.min_net_usd:
                arb_filtered_out_total.labels(reason="profit_low").inc()
                record_arbitrage_proposal(opportunity, filtered_out=True, reason="profit_low")
                continue
            filtered.append(opportunity)
            arb_proposals_after_filter_total.inc()
            arb_net_roi_pct_bucket.observe(max(opportunity.net_roi_pct, 0.0))
            arb_net_profit_usd_bucket.observe(max(opportunity.net_profit_usd, 0.0))
            record_arbitrage_proposal(opportunity, filtered_out=False, reason=None)
        return filtered

    @staticmethod
    def _load_limits(path: Optional[Path]) -> Dict[str, Any]:
        default: Dict[str, Any] = {
            "exchanges": {},
            "symbols": {},
            "slippage_factor": 0.5,
            "transfer_eta_sec": {"internal": 5.0, "chain": 300.0},
        }
        if path is None:
            path = Path("lunia_core/app/infra/limits/arb_limits.yaml")
        if not path.exists():
            return default
        try:
            text = path.read_text(encoding="utf-8")
            data = _parse_simple_yaml(text)
            if isinstance(data, dict):
                merged = default.copy()
                for key, value in data.items():
                    merged[key] = value
                return merged
        except Exception as exc:  # pragma: no cover - config error fallback
            logger.warning("failed to load arb limits: %s", exc)
        return default


def _parse_simple_yaml(text: str) -> Dict[str, Any]:
    """Parse a minimal subset of YAML into Python structures."""

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    stack: List[MutableMapping[str, Any]] = []
    current: MutableMapping[str, Any] = {}
    key_stack: List[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line and not line.startswith("-"):
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value == "":
                new_map: MutableMapping[str, Any] = {}
                current[key] = new_map
                stack.append(current)
                key_stack.append(key)
                current = new_map
            else:
                current[key] = _parse_value(value)
        elif line == "-":
            # minimal support for simple lists
            current.setdefault("items", []).append({})
        elif line == "...":
            continue
        elif line == "---":
            continue
        elif line == "end":
            continue
        elif line == "}":
            if stack:
                current = stack.pop()
                key_stack.pop()
        else:
            # dedent by counting spaces
            indent = len(raw_line) - len(raw_line.lstrip(" "))
            while stack and indent < 2 * len(stack):
                current = stack.pop()
                key_stack.pop()
            if ":" in line:
                key, value = line.split(":", 1)
                current[key.strip()] = _parse_value(value.strip())
    while stack:
        current = stack.pop()
    return current


def _parse_value(value: str) -> Any:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value.strip('"')


__all__ = [
    "ArbitrageScanner",
    "ArbitrageFilters",
    "ArbitrageOpportunity",
]
