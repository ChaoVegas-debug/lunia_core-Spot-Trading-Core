"""Simple in-memory portfolio accounting."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional

from ...db.reporting import record_trade

logger = logging.getLogger(__name__)


@dataclass
class Position:
    symbol: str
    quantity: float = 0.0
    average_price: float = 0.0
    strategy: str | None = None
    stop_pct: float | None = None
    take_pct: float | None = None
    fees_paid: float = 0.0

    def apply_fill(self, side: str, qty: float, price: float) -> float:
        """Apply a fill and return realized PnL impact."""
        logger.debug(
            "Updating position %s side=%s qty=%.8f price=%.2f",
            self.symbol,
            side,
            qty,
            price,
        )
        side_upper = side.upper()
        qty_delta = qty if side_upper == "BUY" else -qty
        realized = 0.0

        if self.quantity != 0 and (self.quantity > 0 > qty_delta or self.quantity < 0 < qty_delta):
            closing_qty = min(abs(self.quantity), abs(qty_delta))
            pnl_per_unit = price - self.average_price
            if self.quantity < 0:
                pnl_per_unit = self.average_price - price
            realized = pnl_per_unit * closing_qty

        new_qty = self.quantity + qty_delta
        if new_qty == 0:
            self.quantity = 0.0
            self.average_price = 0.0
            return realized

        if self.quantity == 0 or (self.quantity > 0 and qty_delta > 0) or (
            self.quantity < 0 and qty_delta < 0
        ):
            # Increasing exposure in same direction
            total_cost = self.average_price * self.quantity + price * qty_delta
            self.average_price = total_cost / new_qty if new_qty else 0.0

        self.quantity = new_qty
        return realized


class Portfolio:
    """Minimal portfolio implementation keeping track of open positions."""

    def __init__(self) -> None:
        self.positions: Dict[str, Position] = {}
        self.market_prices: Dict[str, float] = {}
        self.realized_pnl: float = 0.0

    def update_on_fill(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        *,
        strategy: str | None = None,
        fees: float = 0.0,
        stop_pct: float | None = None,
        take_pct: float | None = None,
    ) -> float:
        logger.info("Applying fill for %s side=%s qty=%.8f price=%.2f", symbol, side, qty, price)
        position = self.positions.setdefault(symbol, Position(symbol=symbol))
        pnl_delta = position.apply_fill(side, qty, price)
        self.market_prices[symbol] = price
        self.realized_pnl += pnl_delta
        position.strategy = strategy or position.strategy
        position.stop_pct = stop_pct if stop_pct is not None else position.stop_pct
        position.take_pct = take_pct if take_pct is not None else position.take_pct
        position.fees_paid += fees
        record_trade(
            timestamp=None,
            symbol=symbol,
            side=side,
            qty=qty,
            price=price,
            pnl=pnl_delta,
            strategy=strategy,
        )
        return pnl_delta

    def mark_price(self, symbol: str, price: float) -> None:
        self.market_prices[symbol] = price

    def get_position(self, symbol: str) -> Optional[Position]:
        return self.positions.get(symbol)

    def unrealized_pnl(self, symbol: str) -> float:
        position = self.positions.get(symbol)
        if not position:
            return 0.0
        mark_price = self.market_prices.get(symbol, position.average_price)
        return (mark_price - position.average_price) * position.quantity

    def total_unrealized(self) -> float:
        return sum(self.unrealized_pnl(symbol) for symbol in self.positions)

    def get_equity_usd(self, balances: Dict[str, float]) -> float:
        """Estimate equity from balances and current marks."""
        equity = balances.get("USDT", 0.0)
        for symbol, position in self.positions.items():
            mark = self.market_prices.get(symbol, position.average_price)
            equity += position.quantity * mark
        return equity + self.realized_pnl

    def open_positions(self) -> int:
        return sum(1 for position in self.positions.values() if abs(position.quantity) > 0)
