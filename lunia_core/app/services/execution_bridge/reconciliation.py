"""
Epoch C.1: Partial Fill Reconciliation

Detects and records partial fills without automatic re-execution.

RULE: NO automatic re-execution — partial fills require MANUAL intervention.
"""
import logging
from typing import Dict

from .models import ExecutionResult, OrderPlan

logger = logging.getLogger(__name__)


class PartialFillReconciler:
    """
    Detects partial fills and computes remaining quantity.
    
    NO AUTOMATIC RE-EXECUTION: Partial fills flagged for manual review.
    """
    
    def reconcile(self, result: ExecutionResult, plan: OrderPlan) -> Dict:
        """
        Reconcile execution result against planned quantity.
        
        Args:
            result: Execution result from adapter
            plan: Original order plan
            
        Returns:
            {
                "status": "FILLED" | "PARTIAL" | "UNFILLED" | "ERROR",
                "filled_qty": float,
                "remaining_qty": float,
                "fill_percentage": float,
                "requires_manual_review": bool
            }
        """
        # Error case
        if not result.executed:
            return {
                "status": "ERROR",
                "filled_qty": 0.0,
                "remaining_qty": plan.quantity,
                "fill_percentage": 0.0,
                "requires_manual_review": True,
                "error_code": result.error_code
            }
        
        filled_qty = result.filled_qty
        planned_qty = plan.quantity
        
        # Calculate remaining
        remaining_qty = max(0.0, planned_qty - filled_qty)
        fill_pct = (filled_qty / planned_qty * 100) if planned_qty > 0 else 0.0
        
        # Determine status
        tolerance = 1e-6  # Floating point tolerance
        
        if abs(remaining_qty) < tolerance:
            # Fully filled
            status = "FILLED"
            requires_review = False
            logger.info(
                f"✅ FILLED: {filled_qty}/{planned_qty} {plan.symbol} "
                f"({fill_pct:.1f}%)"
            )
        
        elif filled_qty < tolerance:
            # Unfilled (edge case)
            status = "UNFILLED"
            requires_review = True
            logger.warning(
                f"⚠️  UNFILLED: 0/{planned_qty} {plan.symbol} "
                f"(executed=True but filled_qty=0)"
            )
        
        else:
            # Partial fill
            status = "PARTIAL"
            requires_review = True
            logger.warning(
                f"⚠️  PARTIAL FILL: {filled_qty}/{planned_qty} {plan.symbol} "
                f"({fill_pct:.1f}%), remaining={remaining_qty}"
            )
        
        return {
            "status": status,
            "filled_qty": filled_qty,
            "remaining_qty": remaining_qty,
            "fill_percentage": round(fill_pct, 2),
            "requires_manual_review": requires_review
        }
