"""Exchange client interfaces."""
from __future__ import annotations

from typing import Dict, Optional, Protocol


class IExchange(Protocol):
    """Interface for exchange clients."""

    def get_price(self, symbol: str) -> float:
        """Return the latest price for the given symbol."""

    def place_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        type: str = "MARKET",
    ) -> Dict[str, object]:
        """Place an order and return exchange response."""

    def cancel_order(self, order_id: str) -> Dict[str, object]:
        """Cancel an existing order."""

    def get_position(self, symbol: str) -> Optional[Dict[str, object]]:
        """Return current position details for the symbol if available."""
