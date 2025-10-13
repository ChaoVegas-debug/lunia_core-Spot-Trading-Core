"""Multi-strategy supervisor that fuses signals and applies capital caps."""
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Deque, Dict, Iterable, List, Mapping, MutableMapping, Optional

from ..capital.allocator import AllocationResult, CapitalAllocator
from ..metrics import signals_total, spot_risk_reject_total
from ..portfolio.portfolio import Portfolio
from ..risk.manager import RiskManager
from ..state import get_state
from .strategies import REGISTRY, StrategySignal

logger = logging.getLogger(__name__)

LOG_PATH = Path(__file__).resolve().parents[4] / "logs" / "supervisor.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def _write_log(message: str) -> None:
    with LOG_PATH.open("a", encoding="utf-8") as fp:
        fp.write(message + "\n")


@dataclass
class Supervisor:
    """Generate ranked trading signals across multiple strategies."""

    client: Optional["IExchange"] = None
    history_limit: int = 200
    risk: Optional[RiskManager] = None
    portfolio: Optional[Portfolio] = None
    price_history: MutableMapping[str, Deque[float]] = field(
        default_factory=lambda: {}
    )
    ai_priorities: MutableMapping[str, float] = field(default_factory=dict)

    def _ensure_history(self, symbol: str) -> Deque[float]:
        history = self.price_history.get(symbol)
        if history is None:
            history = deque(maxlen=self.history_limit)
            self.price_history[symbol] = history
        return history

    def update_price(self, symbol: str, price: float) -> None:
        history = self._ensure_history(symbol)
        history.append(price)

    def _allocator_from_state(self, state: Mapping[str, object]) -> CapitalAllocator:
        spot_cfg = state.get("spot", {})
        return CapitalAllocator(
            max_trade_pct=float(spot_cfg.get("max_trade_pct", 0.20)),
            risk_per_trade_pct=float(spot_cfg.get("risk_per_trade_pct", 0.005)),
            max_symbol_exposure_pct=float(spot_cfg.get("max_symbol_exposure_pct", 0.35)) * 100,
            max_positions=int(spot_cfg.get("max_positions", 5)),
        )

    def _collect_prices(self, symbol: str) -> List[float]:
        history = self.price_history.get(symbol)
        return list(history) if history else []

    def _ai_weight(self, symbol: str) -> float:
        return max(0.1, float(self.ai_priorities.get(symbol, 1.0)))

    def _allocations(
        self,
        *,
        allocator: CapitalAllocator,
        state: Mapping[str, object],
    ) -> AllocationResult:
        spot_cfg = state.get("spot", {})
        reserves = state.get("reserves", {})
        ops_cfg = state.get("ops", {})
        capital_cfg = ops_cfg.get("capital", {}) if isinstance(ops_cfg, Mapping) else {}
        cap_pct = float(capital_cfg.get("cap_pct", 0.25))
        equity = float(state.get("portfolio_equity", 10_000))
        if self.portfolio is not None:
            equity = self.portfolio.get_equity_usd({"USDT": equity})
        weights = spot_cfg.get("weights", {}) if isinstance(spot_cfg, Mapping) else {}
        return allocator.compute_budgets(
            equity=equity,
            cap_pct=cap_pct,
            reserves=reserves,
            weights=weights,
        )

    def _strategy_base(self, strategy_name: str, weights: Mapping[str, float]) -> str:
        if strategy_name in weights:
            return strategy_name
        if "_" in strategy_name:
            candidate = strategy_name.split("_")[0]
            if candidate in weights:
                return candidate
        return strategy_name

    def _compute_qty(self, notional: float, price: float) -> float:
        if price <= 0:
            return 0.0
        return notional / price

    def gather_signals(
        self,
        *,
        symbols: Optional[Iterable[str]] = None,
        context: Optional[Mapping[str, float]] = None,
    ) -> Dict[str, object]:
        runtime = get_state()
        if runtime.get("global_stop") or not runtime.get("trading_on", True):
            logger.info("Supervisor halted by runtime state")
            return {"enable": {"SPOT": 0}, "signals": [], "meta": {"reason": "halted"}}
        spot_cfg = runtime.get("spot", {})
        if not spot_cfg.get("enabled", True):
            return {"enable": {"SPOT": 0}, "signals": [], "meta": {"reason": "spot-disabled"}}

        symbols = list(symbols or [runtime.get("default_pair", "BTCUSDT") or "BTCUSDT"])
        allocator = self._allocator_from_state(runtime)
        allocation = self._allocations(allocator=allocator, state=runtime)

        ctx_extra: Dict[str, float] = dict(context or {})
        ctx_extra.setdefault("sl_pct_default", spot_cfg.get("sl_pct_default", 0.15))
        ctx_extra.setdefault("tp_pct_default", spot_cfg.get("tp_pct_default", 0.30))

        reference_map = {
            sym: self._collect_prices(sym)
            for sym in symbols
        }
        ctx_extra["reference_prices"] = reference_map

        accepted: List[Dict[str, object]] = []
        rejected: List[Dict[str, object]] = []

        weight_map = spot_cfg.get("weights", {}) if isinstance(spot_cfg, Mapping) else {}

        for symbol in symbols:
            try:
                if self.client is not None:
                    latest = self.client.get_price(symbol)
                    self.update_price(symbol, latest)
            except Exception as exc:  # pragma: no cover - network errors
                logger.warning("Failed to refresh price for %s: %s", symbol, exc)
            prices = self._collect_prices(symbol)
            if not prices:
                continue
            for name, strategy in REGISTRY.items():
                ctx_extra.setdefault("orderbook_depth_ratio", context.get("orderbook_depth_ratio", 0.5) if context else 0.5)
                ctx_extra.setdefault("volatility", context.get("volatility", 0.01) if context else 0.01)
                outputs = strategy(symbol, prices, ctx_extra)
                for signal in outputs:
                    base = self._strategy_base(signal.strategy, weight_map)
                    weight = float(weight_map.get(base, 0.0))
                    if weight <= 0:
                        rejected.append({"strategy": signal.strategy, "reason": "weight-zero"})
                        continue
                    priority = self._ai_weight(symbol)
                    combined_score = signal.score * weight * priority
                    notional_cap = allocation.per_strategy.get(base, 0.0)
                    risk_size = allocator.risk_size(
                        equity=allocation.tradable_equity,
                        stop_pct=max(signal.stop_pct, 0.0001),
                    )
                    notional = min(notional_cap, risk_size)
                    qty = self._compute_qty(notional, signal.price)
                    if qty <= 0:
                        rejected.append({"strategy": signal.strategy, "reason": "no-budget"})
                        continue
                    signals_total.labels(symbol=symbol, side=signal.side).inc()
                    accepted.append(
                        {
                            "symbol": symbol,
                            "side": signal.side,
                            "strategy": signal.strategy,
                            "qty": qty,
                            "price": signal.price,
                            "notional_usd": notional,
                            "score": combined_score,
                            "stop_pct": signal.stop_pct,
                            "take_pct": signal.take_pct,
                        }
                    )

        accepted.sort(key=lambda item: item.get("score", 0.0), reverse=True)
        timestamp = datetime.utcnow().isoformat()
        _write_log(f"{timestamp} signals={len(accepted)} rejected={len(rejected)}")
        for entry in rejected:
            spot_risk_reject_total.labels(reason=entry.get("reason", "unknown")).inc()
        return {
            "enable": {"SPOT": 1},
            "signals": accepted,
            "meta": {
                "rejected": rejected,
                "allocation": allocation.per_strategy,
                "tradable_equity": allocation.tradable_equity,
            },
        }

    def get_signals(self, symbol: str = "BTCUSDT") -> Dict[str, object]:
        return self.gather_signals(symbols=[symbol])
