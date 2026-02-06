"""
Epoch C: Order Planner — Pure Deterministic Sizing

Transforms CouncilVerdict → OrderPlan with deterministic qty calculation.
"""
import logging
from typing import Optional, Dict

from ..council.models import CouncilVerdict, CouncilDecision
from .models import OrderIntent, OrderPlan, OrderSide, OrderType, TimeInForce

logger = logging.getLogger(__name__)


class OrderPlanner:
    """
    Pure, deterministic order planner.
    
    Input: CouncilVerdict + equity snapshot
    Output: OrderPlan | None
    
    NO EXECUTION - just planning with sizing logic.
    """
    
    def __init__(self, default_risk_pct: float = 0.01):
        """
        Args:
            default_risk_pct: Default risk per trade (e.g., 0.01 = 1%)
        """
        self.default_risk_pct = default_risk_pct
    
    def plan(
        self,
        verdict: CouncilVerdict,
        equity_snapshot: Optional[Dict] = None,
        reference_price: Optional[float] = None
    ) -> Optional[OrderPlan]:
        """
        Create deterministic order plan.
        
        Returns None if:
        - Verdict not APPROVE
        - Missing required data (equity, price)
        - Market conditions unsafe
        """
        # Gate 1: Council approval required
        if verdict.decision != CouncilDecision.APPROVE:
            logger.info(
                f"Planning aborted: verdict={verdict.decision} (not APPROVE)"
            )
            return None
        
        # Gate 2: Equity snapshot required (safety)
        if equity_snapshot is None:
            logger.warning("Planning aborted: missing equity_snapshot (safety)")
            return None
        
        total_equity = equity_snapshot.get("total_equity", 0)
        if total_equity <= 0:
            logger.warning(f"Planning aborted: invalid equity={total_equity}")
            return None
        
        # Gate 3: Reference price required
        if reference_price is None or reference_price <= 0:
            logger.warning(f"Planning aborted: invalid reference_price={reference_price}")
            return None
        
        # Gate 4: Market safety check (from snapshot)
        market_risk = verdict.market_state_snapshot.get("market_risk_flag", "UNKNOWN")
        if market_risk == "DANGEROUS":
            logger.warning("Planning aborted: market_risk_flag=DANGEROUS")
            return None
        
        # Extract symbol/side from verdict's proposal
        # Note: We need to get this from the ExecutionProposal that created the verdict
        # For now, assume it's in market_state_snapshot (will need integration)
        symbol = verdict.market_state_snapshot.get("symbol", "UNKNOWN")
        side_str = verdict.market_state_snapshot.get("side", "BUY")
        
        # Deterministic Sizing Logic
        risk_amount = total_equity * self.default_risk_pct  # e.g., 1% of $10k = $100
        quantity = risk_amount / reference_price  # e.g., $100 / $50k = 0.002 BTC
        
        # Round to reasonable precision (mock lot size)
        quantity = round(quantity, 6)
        
        if quantity <= 0:
            logger.warning(f"Planning aborted: calculated qty={quantity} <= 0")
            return None
        
        # Build sizing logic audit trail
        sizing_logic = (
            f"Risk {self.default_risk_pct*100:.1f}% of ${total_equity:.2f} equity = "
            f"${risk_amount:.2f} / ${reference_price:.2f} = {quantity:.6f}"
        )
        
        # Create plan
        plan = OrderPlan(
            verdict_id=verdict.id,
            symbol=symbol,
            side=OrderSide(side_str),
            quantity=quantity,
            order_type=OrderType.MARKET,
            limit_price=None,
            time_in_force=TimeInForce.IOC,
            sizing_logic=sizing_logic
        )
        
        logger.info(
            f"Order plan created: {symbol} {side_str} {quantity:.6f} "
            f"(verdict={verdict.id[:8]}..., logic={sizing_logic})"
        )
        
        return plan
