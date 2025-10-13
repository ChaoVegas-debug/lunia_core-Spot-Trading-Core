"""Mock OKX spot exchange client for arbitrage scanning."""
from __future__ import annotations

import logging
from typing import Dict, Optional

from .base import IExchange

logger = logging.getLogger(__name__)


class OKXSpot(IExchange):
    """Lightweight OKX spot client providing deterministic mock prices."""

    def __init__(self, price_map: Optional[Dict[str, float]] = None) -> None:
        self.price_map = price_map or {
            "BTCUSDT": 60050.0,
            "ETHUSDT": 3040.0,
        }

    def get_price(self, symbol: str) -> float:
        price = self.price_map.get(symbol.upper(), 100.0)
        logger.debug("OKX mock price for %s: %.2f", symbol, price)
        return price

    def place_order(self, symbol: str, side: str, qty: float, type: str = "MARKET") -> Dict[str, object]:  # noqa: D401
        logger.info("OKX mock place_order symbol=%s side=%s qty=%.6f", symbol, side, qty)
        return {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "executedQty": qty,
            "price": self.get_price(symbol),
            "status": "FILLED",
            "type": type,
        }

    def cancel_order(self, order_id: str) -> Dict[str, object]:  # noqa: D401
        logger.info("OKX mock cancel_order id=%s", order_id)
        return {"orderId": order_id, "status": "CANCELED"}

    def get_position(self, symbol: str) -> Optional[Dict[str, object]]:  # noqa: D401
        return None
