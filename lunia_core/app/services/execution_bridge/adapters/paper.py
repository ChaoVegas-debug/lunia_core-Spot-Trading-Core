"""
Epoch C: PaperAdapter — Deterministic Fill Simulation

NO real exchange calls - deterministic simulation for testing.
"""
import logging
from typing import Dict

from ..models import OrderPlan, OrderSide

logger = logging.getLogger(__name__)


class PaperAdapter:
    """
    Deterministic paper trading adapter.
    
    Simulates fills using reference_price (no slippage).
    """
    
    def place_order(self, plan: OrderPlan, reference_price: float) -> Dict:
        """
        Simulate order placement.
        
        Returns:
            Dict with exchange_order_id, filled_qty, avg_price
        """
        # Deterministic fill (100% filled at reference price)
        fake_order_id = f"PAPER-{plan.id[:8]}"
        
        logger.info(
            f"📄 PAPER EXECUTION: {plan.symbol} {plan.side} {plan.quantity:.6f} @ ${reference_price:.2f}"
        )

        
        return {
            "exchange_order_id": fake_order_id,
            "filled_qty": plan.quantity,
            "avg_price": reference_price,
            "status": "FILLED"
        }
