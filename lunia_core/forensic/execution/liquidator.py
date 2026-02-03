"""Emergency Liquidator (PHASE 3)

Mechanical tool to generate emergency SELL intent.
Respects Phase 0 sizing rules (stepSize normalization).
REDUCE-ONLY: never increases position.
"""
from decimal import Decimal, ROUND_DOWN
from typing import Dict, Any, Optional


# BTC/USDT standard step size (Binance)
STEP_SIZE = Decimal("0.00001")


class Liquidator:
    """Emergency liquidator - mechanical SELL intent generator.
    
    PHASE 3 SAFETY VALVE:
    - Generates single emergency SELL to liquidate entire position
    - Normalizes quantity using stepSize (Phase 0 compliance)
    - Tracks truncation loss for audit trail
    - NO oversell (crashes if position too small)
    """
    
    @staticmethod
    def generate_emergency_liquidation(
        portfolio_snapshot: Dict[str, Decimal],
        intent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate emergency liquidation intent.
        
        Args:
            portfolio_snapshot: {position_qty: Decimal, ...}
            intent_id: Optional custom intent ID
            
        Returns:
            Emergency SELL intent (dict) ready for risk gate
            
        Raises:
            ValueError: If no position or position too small after normalization
        """
        raw_qty = portfolio_snapshot.get('position_qty', Decimal("0"))
        
        if raw_qty <= Decimal("0"):
            raise ValueError(
                f"[LIQUIDATOR_ERROR] No position to liquidate. "
                f"position_qty={raw_qty}"
            )
        
        # Normalize to stepSize (ROUND_DOWN to avoid oversell)
        normalized_qty = (
            raw_qty / STEP_SIZE
        ).quantize(Decimal("1"), rounding=ROUND_DOWN) * STEP_SIZE
        
        if normalized_qty <= Decimal("0"):
            raise ValueError(
                f"[LIQUIDATOR_ERROR] Position too small after normalization. "
                f"raw_qty={raw_qty}, step_size={STEP_SIZE}, "
                f"normalized_qty={normalized_qty}"
            )
        
        truncation_loss = raw_qty - normalized_qty
        
        # Generate emergency SELL intent
        intent = {
            "id": intent_id or "emergency-liquidation",
            "side": "SELL",
            "order_type": "MARKET",
            "qty": normalized_qty,
            "is_emergency": True,
            "emergency_reason": "PANIC_BUTTON_LIQUIDATION",
            "metadata": {
                "raw_qty": str(raw_qty),
                "normalized_qty": str(normalized_qty),
                "step_size": str(STEP_SIZE),
                "truncation_loss": str(truncation_loss),
                "liquidator": "PHASE3_SAFETY_VALVE"
            }
        }
        
        return intent
