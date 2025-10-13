"""Risk management module."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

LOG_PATH = Path(__file__).resolve().parents[4] / "logs" / "risk.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)


def _append_log(message: str) -> None:
    with LOG_PATH.open("a", encoding="utf-8") as fp:
        fp.write(message + "\n")


@dataclass
class RiskLimits:
    """Static risk limit configuration."""

    max_daily_loss_pct: float = 2.0
    daily_max_drawdown_pct: float | None = None
    max_pos_leverage: float = 10.0
    max_symbol_risk_pct: float = 1.0
    max_symbol_exposure_pct: float = 35.0
    max_concurrent_pos: int = 5


class RiskManager:
    """Validate orders against configured risk limits."""

    def __init__(self, limits: RiskLimits | None = None) -> None:
        self.limits = limits or RiskLimits()
        self.daily_pnl: float = 0.0

    def validate_order(
        self,
        equity_usd: float,
        order_value_usd: float,
        leverage: float,
    ) -> Tuple[bool, str]:
        logger.info(
            "Validating order equity=%.2f value=%.2f leverage=%.2f",
            equity_usd,
            order_value_usd,
            leverage,
        )

        if equity_usd <= 0:
            reason = "equity must be positive"
            logger.warning(reason)
            _append_log(reason)
            return False, reason

        if leverage > self.limits.max_pos_leverage:
            reason = "max leverage exceeded"
            logger.warning(reason)
            _append_log(reason)
            return False, reason

        exposure_pct = 0.0
        if equity_usd > 0:
            exposure_pct = (order_value_usd / equity_usd) * 100 if order_value_usd else 0.0

        if exposure_pct > self.limits.max_symbol_risk_pct:
            reason = "max symbol risk exceeded"
            logger.warning(reason)
            _append_log(reason)
            return False, reason

        if self.daily_pnl < 0:
            reference_equity = equity_usd if equity_usd > 0 else order_value_usd
            if order_value_usd > 0 and reference_equity > 0:
                reference_equity = min(reference_equity, order_value_usd)
            reference_equity = max(reference_equity, 1.0)
            loss_pct = abs(self.daily_pnl) / reference_equity * 100
            limit = self.limits.daily_max_drawdown_pct or self.limits.max_daily_loss_pct
            if loss_pct >= limit:
                reason = "max daily loss exceeded"
                logger.warning(reason)
                _append_log(reason)
                return False, reason

        logger.info("Order validated successfully")
        _append_log("ok")
        return True, ""

    def register_pnl(self, pnl_delta: float) -> None:
        """Update daily PnL tracking."""
        if pnl_delta == 0:
            return
        self.daily_pnl += pnl_delta
        message = f"pnl_delta={pnl_delta:.2f} daily_pnl={self.daily_pnl:.2f}"
        logger.info(message)
        _append_log(message)

    def validate_arbitrage(self, *, qty_usd: float, net_roi_pct: float) -> Tuple[bool, str]:
        """Light-weight validation for arbitrage opportunities."""

        if qty_usd <= 0:
            reason = "invalid notional"
            logger.warning(reason)
            _append_log(reason)
            return False, reason
        if net_roi_pct <= 0:
            reason = "non positive roi"
            logger.warning(reason)
            _append_log(reason)
            return False, reason
        logger.info("Arbitrage opportunity accepted")
        return True, ""

    def validate_spot_order(
        self,
        *,
        equity_usd: float,
        notional_usd: float,
        symbol: str,
        open_positions: int,
        current_symbol_exposure_pct: float,
        limits: dict[str, float] | None = None,
    ) -> Tuple[bool, str]:
        """Validate a prospective spot order against extended limits."""

        limits = limits or {}
        if equity_usd <= 0:
            return False, "insufficient_equity"
        if notional_usd <= 0:
            return False, "invalid_notional"
        min_notional = float(limits.get("min_notional", 0.0))
        if notional_usd < min_notional:
            return False, "min_notional"
        if open_positions >= self.limits.max_concurrent_pos and not limits.get("position_exists", False):
            return False, "max_positions"
        exposure_pct = (notional_usd / equity_usd) * 100.0
        max_symbol_pct = limits.get("max_symbol_exposure_pct", self.limits.max_symbol_exposure_pct)
        if current_symbol_exposure_pct + exposure_pct > max_symbol_pct:
            return False, "over_exposure"
        risk_pct_limit = limits.get("max_symbol_risk_pct", self.limits.max_symbol_risk_pct)
        if exposure_pct > risk_pct_limit:
            return False, "max_symbol_risk"
        if limits.get("lot_size"):
            lot = float(limits["lot_size"])
            if notional_usd < lot:
                return False, "lot"
        if limits.get("tick_size"):
            tick = float(limits["tick_size"])
            if tick > 0 and round(notional_usd / tick) <= 0:
                return False, "tick"
        if self.daily_pnl < 0:
            reference_equity = equity_usd if equity_usd > 0 else notional_usd
            if notional_usd > 0 and reference_equity > 0:
                reference_equity = min(reference_equity, notional_usd)
            reference_equity = max(reference_equity, 1.0)
            loss_pct = abs(self.daily_pnl) / reference_equity * 100
            limit = self.limits.daily_max_drawdown_pct or self.limits.max_daily_loss_pct
            if loss_pct >= limit:
                return False, "max_daily_loss"
        logger.info(
            "Spot order validated symbol=%s notional=%.2f open_positions=%d", symbol, notional_usd, open_positions
        )
        return True, ""
