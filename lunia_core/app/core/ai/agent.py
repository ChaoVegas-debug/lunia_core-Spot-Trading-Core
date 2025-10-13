"""Trading agent implementation."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from ..bus import get_bus
from ..exchange.base import IExchange
from ..metrics import (
    orders_rejected_total,
    orders_total,
    pnl_total,
    spot_daily_pnl_usd,
    spot_positions_open,
    spot_pnl_total_usd,
    spot_risk_reject_total,
    spot_success_rate_pct,
    spot_trades_total,
)
from ..state import get_state
from ..portfolio.portfolio import Portfolio
from ..risk.manager import RiskManager
from .supervisor import Supervisor

logger = logging.getLogger(__name__)
LOG_PATH = Path(__file__).resolve().parents[4] / "logs" / "trades.jsonl"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class Agent:
    """Trading agent executing spot orders with risk checks and journaling."""

    client: IExchange
    risk: RiskManager
    supervisor: Supervisor
    portfolio: Portfolio = field(default_factory=Portfolio)
    default_equity_usd: float = 10_000.0
    subscribe_bus: bool = True
    bus: object = field(init=False, repr=False, default=None)
    executed_count: int = 0
    success_count: int = 0
    daily_pnl: float = 0.0

    def __post_init__(self) -> None:
        self.bus = get_bus()
        if self.subscribe_bus and self.bus:
            self.bus.subscribe("signals", self._handle_signal)
        if hasattr(self.supervisor, "risk"):
            self.supervisor.risk = self.risk
        if hasattr(self.supervisor, "portfolio"):
            self.supervisor.portfolio = self.portfolio

    def _handle_signal(self, message: Dict[str, object]) -> None:
        logger.info("Agent received signal via bus: %s", message)
        signals = {"signals": [message], "enable": {"SPOT": 1}}
        self.execute_signals(signals)

    def place_spot_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        *,
        price: Optional[float] = None,
        strategy: str | None = None,
        stop_pct: float | None = None,
        take_pct: float | None = None,
        notional_usd: float | None = None,
    ) -> Dict[str, object]:
        runtime = get_state()
        if runtime.get("global_stop") or not runtime.get("trading_on", True):
            reason = "trading halted"
            logger.warning("Skipping order due to runtime state: %s", reason)
            orders_rejected_total.labels(symbol=symbol, side=side.upper(), reason=reason).inc()
            spot_risk_reject_total.labels(reason=reason).inc()
            return {"ok": False, "reason": reason}
        side_upper = side.upper()
        logger.info("Agent received spot order symbol=%s side=%s qty=%.8f", symbol, side_upper, qty)
        market_price = price or self.client.get_price(symbol)
        notional = notional_usd if notional_usd is not None else market_price * qty
        equity_runtime = runtime.get("portfolio_equity", self.default_equity_usd)
        portfolio_equity = self.portfolio.get_equity_usd({"USDT": equity_runtime})
        equity = max(portfolio_equity, equity_runtime)
        position = self.portfolio.get_position(symbol)
        current_exposure = 0.0
        if position and equity > 0:
            current_exposure = abs(position.quantity * market_price) / equity * 100
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "symbol": symbol,
            "side": side_upper,
            "qty": qty,
            "price": market_price,
            "status": "PENDING",
            "reason": "",
            "strategy": strategy,
        }
        ok, reason = self.risk.validate_order(
            equity_usd=equity,
            order_value_usd=notional,
            leverage=1.0,
        )
        if not ok:
            record["reason"] = reason
            record["status"] = "REJECTED"
            logger.warning("Risk validation failed: %s", reason)
            orders_rejected_total.labels(symbol=symbol, side=side_upper, reason=reason).inc()
            spot_risk_reject_total.labels(reason=reason).inc()
            self._log_trade(record)
            return {"ok": False, "reason": reason}

        ok, reason = self.risk.validate_spot_order(
            equity_usd=equity,
            notional_usd=notional,
            symbol=symbol,
            open_positions=self.portfolio.open_positions(),
            current_symbol_exposure_pct=current_exposure,
            limits={
                "position_exists": bool(position and position.quantity != 0),
                "max_symbol_exposure_pct": runtime["spot"].get("max_symbol_exposure_pct", 0.35) * 100,
                "max_symbol_risk_pct": self.risk.limits.max_symbol_risk_pct,
                "equity": equity,
            },
        )
        if not ok:
            record["reason"] = reason
            record["status"] = "REJECTED"
            logger.warning("Risk validation failed: %s", reason)
            orders_rejected_total.labels(symbol=symbol, side=side_upper, reason=reason).inc()
            spot_risk_reject_total.labels(reason=reason).inc()
            self._log_trade(record)
            return {"ok": False, "reason": reason}

        response = self.client.place_order(symbol, side_upper, qty)
        orders_total.labels(symbol=symbol, side=side_upper).inc()
        spot_trades_total.labels(strategy=strategy or "unknown", symbol=symbol, side=side_upper).inc()
        record.update(
            {
                "status": response.get("status", "FILLED"),
                "order_id": response.get("orderId"),
                "response": response,
            }
        )

        fill_price = float(response.get("price") or market_price)
        fill_qty = float(response.get("executedQty", qty))
        pnl_delta = self.portfolio.update_on_fill(
            symbol,
            side_upper,
            fill_qty,
            fill_price,
            strategy=strategy,
            stop_pct=stop_pct,
            take_pct=take_pct,
        )
        self.risk.register_pnl(pnl_delta)
        pnl_total.set(self.portfolio.realized_pnl)
        spot_pnl_total_usd.set(self.portfolio.realized_pnl)
        self.daily_pnl += pnl_delta
        spot_daily_pnl_usd.set(self.daily_pnl)
        spot_positions_open.set(self.portfolio.open_positions())

        logger.info("Order executed with status %s", record["status"])
        self._log_trade(record)
        return {"ok": True, "order": response}

    def execute_signals(self, decision: Optional[Dict[str, object]] = None) -> Dict[str, List[Dict[str, object]]]:
        runtime = get_state()
        if runtime.get("global_stop"):
            logger.info("Global stop active; no signals executed")
            return {"executed": [], "errors": [{"reason": "global-stop"}]}
        if not runtime.get("trading_on", True):
            logger.info("Trading disabled by runtime state")
            return {"executed": [], "errors": [{"reason": "trading-off"}]}
        if decision is None:
            decision = self.supervisor.get_signals()
        executed: List[Dict[str, object]] = []
        errors: List[Dict[str, object]] = []

        total_processed = 0
        successful = 0
        for signal in decision.get("signals", []):
            symbol = str(signal.get("symbol", "BTCUSDT"))
            side = str(signal.get("side", "BUY")).upper()
            qty = float(signal.get("qty", 0.0))
            price = float(signal.get("price") or self.client.get_price(symbol))
            notional = float(signal.get("notional_usd", price * qty))
            if qty <= 0 and notional > 0:
                qty = notional / price
            if qty <= 0:
                reason = "invalid-qty"
                orders_rejected_total.labels(symbol=symbol, side=side, reason=reason).inc()
                errors.append({"symbol": symbol, "side": side, "reason": reason})
                continue
            result = self.place_spot_order(
                symbol,
                side,
                qty,
                price=price,
                strategy=str(signal.get("strategy", "generic")),
                stop_pct=float(signal.get("stop_pct", 0.0) or 0.0),
                take_pct=float(signal.get("take_pct", 0.0) or 0.0),
                notional_usd=notional,
            )
            total_processed += 1
            if result.get("ok"):
                order = result["order"]
                executed.append(
                    {
                        "symbol": symbol,
                        "side": side,
                        "status": order.get("status", "FILLED"),
                    }
                )
                successful += 1
            else:
                errors.append(
                    {
                        "symbol": symbol,
                        "side": side,
                        "reason": result.get("reason", ""),
                    }
                )

        if total_processed:
            self.executed_count += total_processed
            self.success_count += successful
            ratio = self.success_count / max(self.executed_count, 1)
            spot_success_rate_pct.set(ratio * 100)

        return {"executed": executed, "errors": errors}

    def run_demo_cycle(self) -> None:  # pragma: no cover - long-running loop
        from ..metrics import ensure_metrics_server

        ensure_metrics_server(9101)
        while True:
            results = self.execute_signals()
            logger.info("Demo cycle executed: %s", results)
            time.sleep(60)

    def _log_trade(self, record: Dict[str, object]) -> None:
        with LOG_PATH.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(record) + "\n")
        logger.debug("Trade logged: %s", record)
