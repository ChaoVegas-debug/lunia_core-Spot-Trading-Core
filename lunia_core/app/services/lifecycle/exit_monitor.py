"""
Exit Monitor — Autonomous Exit Evaluation

Monitors active positions and generates exit orders when:
- Stop loss hit
- Take profit hit
- Time expiry reached
- Trailing stop triggered
"""
import logging
from typing import Dict, List, Optional, Tuple

from lunia_core.app.services.lifecycle.models import ExitPlan
from lunia_core.app.services.risk_governor.models import PortfolioSnapshot, Position

logger = logging.getLogger(__name__)


class ExitIntent:
    """
    Exit order intent (to be sent to Council).
    
    Lightweight DTO for exit order generation.
    """
    
    def __init__(
        self,
        symbol: str,
        side: str,  # Exit side (opposite of position)
        quantity: float,
        reason: str,
        reduce_only: bool = True,
        high_priority: bool = True,
    ):
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.reason = reason
        self.reduce_only = reduce_only
        self.high_priority = high_priority
    
    def __repr__(self):
        return (
            f"ExitIntent({self.symbol} {self.side} {self.quantity} "
            f"reason={self.reason} reduce_only={self.reduce_only})"
        )


class ExitMonitor:
    """
    Autonomous exit evaluator.
    
    Evaluates all active exit plans on every tick and generates
    exit intents when trigger conditions are met.
    
    RULES:
    - All exits are reduce_only=True
    - Trailing stops move only in favorable direction
    - First trigger wins (SL before TP, etc.)
    """
    
    def evaluate_exits(
        self,
        exit_plans: Dict[str, ExitPlan],
        snapshot: PortfolioSnapshot,
        now_ms: int,
    ) -> Tuple[List[ExitIntent], Dict[str, ExitPlan]]:
        """
        Evaluate all exit plans and generate exit orders.
        
        Args:
            exit_plans: Active exit plans by symbol
            snapshot: Current portfolio snapshot
            now_ms: Current timestamp
        
        Returns:
            (exit_intents, updated_exit_plans)
            
            exit_intents: List of orders to execute
            updated_exit_plans: Plans with updated trailing stops
        """
        exit_intents: List[ExitIntent] = []
        updated_plans: Dict[str, ExitPlan] = {}
        
        for position in snapshot.positions:
            plan = exit_plans.get(position.symbol)
            if not plan:
                logger.warning(
                    f"⚠️ Position {position.symbol} has NO EXIT PLAN (invalid state)"
                )
                continue
            
            current_price = snapshot.prices.get(position.symbol)
            if not current_price:
                logger.warning(
                    f"Missing price for {position.symbol}, cannot evaluate exits"
                )
                continue
            
            # Check exits in priority order
            exit_intent = self._check_stop_loss(plan, position, current_price)
            if exit_intent:
                exit_intents.append(exit_intent)
                continue
            
            exit_intent = self._check_take_profit(plan, position, current_price)
            if exit_intent:
                exit_intents.append(exit_intent)
                continue
            
            exit_intent = self._check_time_expiry(plan, position, now_ms)
            if exit_intent:
                exit_intents.append(exit_intent)
                continue
            
            # Check trailing stop (may update plan)
            updated_plan = self._check_trailing_stop(
                plan, position, current_price, now_ms
            )
            if updated_plan != plan:
                updated_plans[position.symbol] = updated_plan
        
        return exit_intents, updated_plans
    
    def _check_stop_loss(
        self,
        plan: ExitPlan,
        position: Position,
        current_price: float,
    ) -> Optional[ExitIntent]:
        """Check if stop loss triggered"""
        if not plan.stop_loss_price:
            return None
        
        # LONG: exit if price <= SL
        # SHORT: exit if price >= SL
        if plan.side == "LONG":
            if current_price <= plan.stop_loss_price:
                logger.info(
                    f"🛑 STOP LOSS: {plan.symbol} LONG @ {current_price:.2f} "
                    f"<= SL {plan.stop_loss_price:.2f}"
                )
                return ExitIntent(
                    symbol=plan.symbol,
                    side="SELL",  # Exit LONG
                    quantity=position.quantity,
                    reason="STOP_LOSS",
                    reduce_only=True,
                    high_priority=True,
                )
        else:  # SHORT
            if current_price >= plan.stop_loss_price:
                logger.info(
                    f"🛑 STOP LOSS: {plan.symbol} SHORT @ {current_price:.2f} "
                    f">= SL {plan.stop_loss_price:.2f}"
                )
                return ExitIntent(
                    symbol=plan.symbol,
                    side="BUY",  # Exit SHORT
                    quantity=position.quantity,
                    reason="STOP_LOSS",
                    reduce_only=True,
                    high_priority=True,
                )
        
        return None
    
    def _check_take_profit(
        self,
        plan: ExitPlan,
        position: Position,
        current_price: float,
    ) -> Optional[ExitIntent]:
        """Check if take profit triggered"""
        if not plan.take_profit_price:
            return None
        
        # LONG: exit if price >= TP
        # SHORT: exit if price <= TP
        if plan.side == "LONG":
            if current_price >= plan.take_profit_price:
                logger.info(
                    f"🎯 TAKE PROFIT: {plan.symbol} LONG @ {current_price:.2f} "
                    f">= TP {plan.take_profit_price:.2f}"
                )
                return ExitIntent(
                    symbol=plan.symbol,
                    side="SELL",
                    quantity=position.quantity,
                    reason="TAKE_PROFIT",
                    reduce_only=True,
                    high_priority=True,
                )
        else:  # SHORT
            if current_price <= plan.take_profit_price:
                logger.info(
                    f"🎯 TAKE PROFIT: {plan.symbol} SHORT @ {current_price:.2f} "
                    f"<= TP {plan.take_profit_price:.2f}"
                )
                return ExitIntent(
                    symbol=plan.symbol,
                    side="BUY",
                    quantity=position.quantity,
                    reason="TAKE_PROFIT",
                    reduce_only=True,
                    high_priority=True,
                )
        
        return None
    
    def _check_time_expiry(
        self,
        plan: ExitPlan,
        position: Position,
        now_ms: int,
    ) -> Optional[ExitIntent]:
        """Check if position exceeded max duration"""
        if not plan.max_duration_ms:
            return None
        
        age_ms = now_ms - plan.created_at_ms
        if age_ms >= plan.max_duration_ms:
            logger.info(
                f"⏱️ TIME EXPIRY: {plan.symbol} age {age_ms}ms "
                f">= max {plan.max_duration_ms}ms"
            )
            return ExitIntent(
                symbol=plan.symbol,
                side="SELL" if plan.side == "LONG" else "BUY",
                quantity=position.quantity,
                reason="TIME_EXPIRY",
                reduce_only=True,
                high_priority=True,
            )
        
        return None
    
    def _check_trailing_stop(
        self,
        plan: ExitPlan,
        position: Position,
        current_price: float,
        now_ms: int,
    ) -> ExitPlan:
        """
        Evaluate trailing stop and update if needed.
        
        Returns updated plan (may be same as input if no update).
        """
        if not plan.trailing_stop_activation_price:
            return plan
        
        if not plan.trailing_stop_callback_pct:
            return plan
        
        # Check if trailing activated
        if plan.side == "LONG":
            activated = current_price >= plan.trailing_stop_activation_price
        else:  # SHORT
            activated = current_price <= plan.trailing_stop_activation_price
        
        if not activated:
            return plan
        
        # Track peak price
        if plan.trailing_stop_peak_price is None:
            # First activation
            new_peak = current_price
        else:
            # Update peak
            if plan.side == "LONG":
                new_peak = max(plan.trailing_stop_peak_price, current_price)
            else:  # SHORT
                new_peak = min(plan.trailing_stop_peak_price, current_price)
        
        # Calculate new trailing SL (moves only favorably)
        if plan.side == "LONG":
            new_stop = new_peak * (1 - plan.trailing_stop_callback_pct)
            
            # Only update if new SL is HIGHER (favorable)
            if plan.stop_loss_price is None or new_stop > plan.stop_loss_price:
                logger.debug(
                    f"📈 Trailing SL updated: {plan.symbol} LONG "
                    f"{plan.stop_loss_price:.2f} → {new_stop:.2f}"
                )
                return plan.with_updated_trailing_stop(
                    new_peak_price=new_peak,
                    new_stop_loss=new_stop,
                    now_ms=now_ms,
                )
        
        else:  # SHORT
            new_stop = new_peak * (1 + plan.trailing_stop_callback_pct)
            
            # Only update if new SL is LOWER (favorable)
            if plan.stop_loss_price is None or new_stop < plan.stop_loss_price:
                logger.debug(
                    f"📉 Trailing SL updated: {plan.symbol} SHORT "
                    f"{plan.stop_loss_price:.2f} → {new_stop:.2f}"
                )
                return plan.with_updated_trailing_stop(
                    new_peak_price=new_peak,
                    new_stop_loss=new_stop,
                    now_ms=now_ms,
                )
        
        return plan
