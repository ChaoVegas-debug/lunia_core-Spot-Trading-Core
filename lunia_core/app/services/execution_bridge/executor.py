"""
Epoch C: Order Executor — Side Effects (with Dry-Run)

Executes OrderPlan via adapter (or simulates in dry-run mode).
"""
import logging
from typing import Optional

from .models import OrderPlan, ExecutionResult

logger = logging.getLogger(__name__)


class OrderExecutor:
    """
    Order executor with dry-run support.
    
    SIDE EFFECTS: Calls exchange adapter to place orders.
    """
    
    def execute(
        self,
        plan: OrderPlan,
        adapter,
        reference_price: float,
        dry_run: bool = False
    ) -> ExecutionResult:
        """
        Execute order plan.
        
        Args:
            plan: OrderPlan to execute
            adapter: Exchange adapter (e.g., PaperAdapter)
            reference_price: Reference price for execution
            dry_run: If True, simulate without calling adapter
            
        Returns:
            ExecutionResult with success/failure details
        """
        if dry_run:
            # DRY RUN: Log only, don't call adapter
            logger.info(
                f"🔵 DRY RUN: {plan.symbol} {plan.side} {plan.quantity:.6f} "
                f"@ ${reference_price:.2f} (verdict={plan.verdict_id[:8]}...)"
            )
            
            return ExecutionResult(
                plan_id=plan.id,
                verdict_id=plan.verdict_id,
                executed=True,  # Simulated success
                exchange_order_id=f"DRY-RUN-{plan.id[:8]}",
                filled_qty=plan.quantity,
                avg_price=reference_price,
                error_code=None,
                error_detail=None
            )
        
        # REAL EXECUTION: Call adapter
        try:
            logger.info(
                f"🚀 EXECUTING: {plan.symbol} {plan.side} {plan.quantity:.6f} "
                f"via {adapter.__class__.__name__}"
            )
            
            response = adapter.place_order(plan, reference_price)
            
            # Handle both Dict (legacy) and ExecutionResult (new) return types
            if isinstance(response, ExecutionResult):
                return response
            
            # Legacy Dict return
            return ExecutionResult(
                plan_id=plan.id,
                verdict_id=plan.verdict_id,
                executed=True,
                exchange_order_id=response.get("exchange_order_id"),
                filled_qty=response.get("filled_qty", 0),
                avg_price=response.get("avg_price"),
                error_code=None,
                error_detail=None
            )
        
        except Exception as e:
            # Fail-safe: Adapter error doesn't crash system
            logger.error(
                f"Execution failed for plan {plan.id[:8]}: {e}",
                exc_info=True
            )
            
            return ExecutionResult(
                plan_id=plan.id,
                verdict_id=plan.verdict_id,
                executed=False,
                exchange_order_id=None,
                filled_qty=0,
                avg_price=None,
                error_code="ADAPTER_ERROR",
                error_detail=str(e)[:200]
            )
