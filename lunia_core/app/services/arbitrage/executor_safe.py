"""Safe arbitrage executor with dry-run and double confirmation guards."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.compat.dotenv import load_dotenv
from app.core.metrics import (
    arb_execution_latency_ms,
    arb_execs_total,
    arb_fail_total,
    arb_net_profit_total_usd,
    arb_success_total,
)
from app.core.portfolio.portfolio import Portfolio
from app.core.risk.manager import RiskManager
from app.core.risk.rate_limit import RateLimiter, RateLimitConfig
from app.core.state import get_state
from app.db.reporting import record_arbitrage_execution

from .scanner import ArbitrageOpportunity
from .transfer import TransferResult, internal_transfer, withdraw_and_deposit

load_dotenv()

LOG_PATH = Path(__file__).resolve().parents[4] / "logs" / "arbitrage_exec.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


@dataclass
class ArbitrageExecutionResult:
    """Result of a safe arbitrage execution attempt."""

    exec_id: str
    proposal_id: str
    mode: str
    status: str
    started_at: float
    completed_at: float
    pnl_usd: float
    fees_usd: float
    message: str
    steps: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exec_id": self.exec_id,
            "proposal_id": self.proposal_id,
            "mode": self.mode,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "pnl_usd": self.pnl_usd,
            "fees_usd": self.fees_usd,
            "message": self.message,
            "steps": self.steps,
        }


class SafeArbitrageExecutor:
    """Executes arbitrage in dry/simulation mode with guard rails."""

    def __init__(
        self,
        portfolio: Portfolio,
        risk: RiskManager,
        *,
        admin_pin_hash: Optional[str] = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self.portfolio = portfolio
        self.risk = risk
        self.admin_pin_hash = admin_pin_hash or os.getenv("ADMIN_PIN_HASH", "")
        self.total_pnl = 0.0
        self.rate_limiter = rate_limiter or RateLimiter(RateLimitConfig())

    def _verify_pin(self, pin: Optional[str]) -> bool:
        if not self.admin_pin_hash:
            return True
        if not pin:
            return False
        digest = hashlib.sha256(pin.encode("utf-8")).hexdigest()
        return digest == self.admin_pin_hash

    def execute(
        self,
        opportunity: ArbitrageOpportunity,
        *,
        mode: Optional[str] = None,
        transfer_preference: str = "auto",
        pin: Optional[str] = None,
        double_confirm: bool = False,
        auto_trigger: bool = False,
    ) -> ArbitrageExecutionResult:
        state = get_state()
        if state.get("global_stop"):
            raise RuntimeError("Global stop enabled")
        mode = (mode or state.get("exec_mode") or "dry").lower()
        if mode not in {"dry", "simulation", "real"}:
            raise ValueError("mode must be dry, simulation or real")
        exec_id = str(uuid.uuid4())
        start = time.time()
        steps: List[Dict[str, Any]] = []
        arb_execs_total.labels(mode=mode).inc()

        if self.rate_limiter:
            allowed, reason = self.rate_limiter.allow(
                opportunity.buy_exchange,
                opportunity.sell_exchange,
                opportunity.symbol,
            )
            if not allowed:
                arb_fail_total.labels(mode=mode, stage="rate_limit").inc()
                raise ValueError(reason)

        if mode == "real":
            if not double_confirm:
                arb_fail_total.labels(mode=mode, stage="confirm").inc()
                raise ValueError("double confirmation required for real mode")
            if not self._verify_pin(pin):
                arb_fail_total.labels(mode=mode, stage="pin").inc()
                raise ValueError("invalid PIN")

        ok, reason = self.risk.validate_arbitrage(
            qty_usd=opportunity.qty_usd,
            net_roi_pct=opportunity.net_roi_pct,
        )
        if not ok:
            arb_fail_total.labels(mode=mode, stage="arb_check").inc()
            raise ValueError(f"arbitrage rejected: {reason}")

        ok, reason = self.risk.validate_order(
            equity_usd=max(state.get("portfolio_equity", 1.0), opportunity.qty_usd * 2),
            order_value_usd=opportunity.qty_usd,
            leverage=1.0,
        )
        if not ok:
            arb_fail_total.labels(mode=mode, stage="risk").inc()
            raise ValueError(f"risk rejected: {reason}")

        steps.append({"stage": "reserve", "status": "ok", "qty_usd": opportunity.qty_usd})

        asset_qty = opportunity.qty_usd / max(opportunity.buy_price, 1e-6)
        steps.append(
            {
                "stage": "buy",
                "status": "ok",
                "exchange": opportunity.buy_exchange,
                "price": opportunity.buy_price,
                "qty": asset_qty,
            }
        )
        self.portfolio.update_on_fill(
            symbol=opportunity.symbol,
            side="BUY",
            qty=asset_qty,
            price=opportunity.buy_price,
        )

        transfer_result = self._handle_transfer(opportunity, transfer_preference)
        steps.append({"stage": "transfer", **transfer_result.to_dict()})

        steps.append(
            {
                "stage": "sell",
                "status": "ok",
                "exchange": opportunity.sell_exchange,
                "price": opportunity.sell_price,
                "qty": asset_qty,
            }
        )
        sell_pnl = self.portfolio.update_on_fill(
            symbol=opportunity.symbol,
            side="SELL",
            qty=asset_qty,
            price=opportunity.sell_price,
        )

        pnl_usd = sell_pnl or opportunity.net_profit_usd
        fees_usd = opportunity.meta.get("fees", {}).get("transfer_fee_usd", 0.0)
        steps.append(
            {
                "stage": "settle",
                "status": "ok",
                "pnl_usd": pnl_usd,
                "fees_usd": fees_usd,
            }
        )
        self.total_pnl += pnl_usd
        completed = time.time()
        arb_success_total.labels(mode=mode).inc()
        arb_net_profit_total_usd.set(self.total_pnl)
        arb_execution_latency_ms.labels(mode=mode).observe((completed - start) * 1000)
        if self.rate_limiter:
            self.rate_limiter.record(
                opportunity.buy_exchange,
                opportunity.sell_exchange,
                opportunity.symbol,
            )

        result = ArbitrageExecutionResult(
            exec_id=exec_id,
            proposal_id=opportunity.proposal_id,
            mode=mode,
            status="FILLED",
            started_at=start,
            completed_at=completed,
            pnl_usd=pnl_usd,
            fees_usd=fees_usd,
            message="executed",
            steps=steps,
        )
        self._write_log(result)
        record_arbitrage_execution(result, auto_trigger=auto_trigger)
        return result

    def _handle_transfer(
        self, opportunity: ArbitrageOpportunity, transfer_preference: str
    ) -> TransferResult:
        transfer_type = opportunity.transfer_type
        if transfer_preference == "internal":
            transfer_type = "internal"
        elif transfer_preference == "chain":
            transfer_type = "chain"
        if transfer_type == "internal":
            return internal_transfer(
                opportunity.buy_exchange,
                opportunity.sell_exchange,
                opportunity.symbol,
                opportunity.qty_usd / max(opportunity.buy_price, 1e-6),
            )
        fee_usd = opportunity.meta.get("fees", {}).get("transfer_fee_usd", 0.0)
        eta = opportunity.meta.get("transfer", {}).get("eta_sec", 300.0)
        return withdraw_and_deposit(
            opportunity.buy_exchange,
            opportunity.sell_exchange,
            opportunity.symbol,
            opportunity.qty_usd / max(opportunity.buy_price, 1e-6),
            fee_usd=fee_usd,
            eta_sec=float(eta),
        )

    def _write_log(self, result: ArbitrageExecutionResult) -> None:
        payload = json.dumps(result.to_dict())
        logger.info(payload)


__all__ = ["SafeArbitrageExecutor", "ArbitrageExecutionResult"]
