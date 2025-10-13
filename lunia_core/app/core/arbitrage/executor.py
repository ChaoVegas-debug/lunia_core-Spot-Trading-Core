"""Arbitrage execution helpers."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Mapping

from ..metrics import arbitrage_executed_total, arbitrage_pnl_total
from ..portfolio.portfolio import Portfolio
from ..risk.manager import RiskManager

BASE_LOG_DIR = Path(__file__).resolve().parents[4] / "logs"
LOG_PATH = BASE_LOG_DIR / "arbitrage_exec.log"
TRADES_LOG_PATH = BASE_LOG_DIR / "trades.jsonl"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


@dataclass
class ExecutionResult:
    status: str
    mode: str
    pnl: float
    reason: str = ""
    opportunity: Mapping[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "status": self.status,
            "mode": self.mode,
            "pnl": self.pnl,
            "reason": self.reason,
            "opportunity": dict(self.opportunity),
        }


class ArbitrageExecutor:
    """Execute arbitrage opportunities in simulation or mock mode."""

    def __init__(
        self,
        portfolio: Portfolio,
        risk: RiskManager,
        mode: str = "simulation",
        default_equity_usd: float = 25_000.0,
    ) -> None:
        self.portfolio = portfolio
        self.risk = risk
        self.mode = mode
        self.default_equity_usd = default_equity_usd
        self.fee_pct = float(os.getenv("ARB_FEE_PCT", "0.06"))
        self.slippage_pct = float(os.getenv("ARB_SLIPPAGE_PCT", "0.02"))
        self.total_pnl: float = 0.0

    def _risk_check(self, notional: float) -> tuple[bool, str]:
        return self.risk.validate_order(
            equity_usd=self.default_equity_usd,
            order_value_usd=notional,
            leverage=1.0,
        )

    def _log_trade_leg(self, leg: Dict[str, object]) -> None:
        TRADES_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with TRADES_LOG_PATH.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(leg) + "\n")

    def execute(self, opportunity: Mapping[str, object], qty_usd: float) -> ExecutionResult:
        logger.info("Executing arbitrage opportunity: %s", opportunity)
        buy_px = float(opportunity["buy_px"])
        sell_px = float(opportunity["sell_px"])
        symbol = str(opportunity["symbol"])
        buy_ex = str(opportunity["buy_ex"])
        sell_ex = str(opportunity["sell_ex"])

        qty_base = qty_usd / buy_px if buy_px else 0.0
        effective_buy = buy_px * (1 + self.slippage_pct / 100)
        effective_sell = sell_px * (1 - self.slippage_pct / 100)
        notional_buy = qty_base * effective_buy
        notional_sell = qty_base * effective_sell

        ok_buy, reason = self._risk_check(notional_buy)
        if not ok_buy:
            logger.warning("Arbitrage rejected on buy leg: %s", reason)
            arbitrage_executed_total.labels(mode=self.mode, status="rejected").inc()
            return ExecutionResult(status="REJECTED", mode=self.mode, pnl=0.0, reason=reason, opportunity=opportunity)

        ok_sell, reason = self._risk_check(notional_sell)
        if not ok_sell:
            logger.warning("Arbitrage rejected on sell leg: %s", reason)
            arbitrage_executed_total.labels(mode=self.mode, status="rejected").inc()
            return ExecutionResult(status="REJECTED", mode=self.mode, pnl=0.0, reason=reason, opportunity=opportunity)

        fees = (notional_buy + notional_sell) * (self.fee_pct / 100)
        pnl = notional_sell - notional_buy - fees
        self.total_pnl += pnl
        self.risk.register_pnl(pnl)
        arbitrage_executed_total.labels(mode=self.mode, status="filled").inc()
        arbitrage_pnl_total.set(self.total_pnl)

        if self.mode in {"mock", "simulation"}:
            leg_buy = {
                "timestamp": opportunity.get("ts"),
                "symbol": symbol,
                "exchange": buy_ex,
                "side": "BUY",
                "qty": qty_base,
                "price": effective_buy,
                "status": "FILLED",
                "mode": self.mode,
            }
            leg_sell = {
                "timestamp": opportunity.get("ts"),
                "symbol": symbol,
                "exchange": sell_ex,
                "side": "SELL",
                "qty": qty_base,
                "price": effective_sell,
                "status": "FILLED",
                "mode": self.mode,
            }
            if self.mode == "mock":
                self._log_trade_leg(leg_buy)
                self._log_trade_leg(leg_sell)
                self.portfolio.update_on_fill(symbol, "BUY", qty_base, effective_buy)
                pnl_leg = self.portfolio.update_on_fill(symbol, "SELL", qty_base, effective_sell)
                logger.info("Portfolio updated with mock arbitrage legs (PnL %.2f)", pnl_leg)
            else:
                logger.info("Simulation legs computed (no portfolio update)")

        logger.info("Arbitrage executed pnl=%.2f mode=%s", pnl, self.mode)
        logger.debug("Effective prices buy=%.2f sell=%.2f qty=%.6f", effective_buy, effective_sell, qty_base)

        return ExecutionResult(
            status="FILLED",
            mode=self.mode,
            pnl=pnl,
            reason="",
            opportunity=opportunity,
        )
