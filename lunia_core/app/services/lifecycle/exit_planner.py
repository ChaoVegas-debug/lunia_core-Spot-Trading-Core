"""
Exit Plan Generator — Strategy-Specific Exit Rules

Creates ExitPlan based on strategy type:
- TREND: Wide SL, trailing enabled
- MEAN_REVERSION: Tight SL, fixed TP
- BREAKOUT: Time-based exit
"""
from typing import Optional

from lunia_core.app.services.lifecycle.models import ExitPlan


class ExitPlanner:
    """
    Generates strategy-appropriate exit plans.
    
    Exit plans are MANDATORY at position entry.
    Strategy type determines exit structure.
    """
    
    def create_exit_plan(
        self,
        position_id: str,
        symbol: str,
        side: str,
        entry_price: float,
        strategy_type: str,
        atr: Optional[float],
        now_ms: int,
    ) -> ExitPlan:
        """
        Generate exit plan for position.
        
        Args:
            position_id: Unique position identifier
            symbol: Trading symbol
            side: LONG or SHORT
            entry_price: Entry price
            strategy_type: TREND, MEAN_REVERSION, or BREAKOUT
            atr: Average True Range (for SL/TP calculation)
            now_ms: Current timestamp
        
        Returns:
            Immutable ExitPlan
        
        Raises:
            ValueError: If strategy_type unknown or ATR missing when required
        """
        if side not in ("LONG", "SHORT"):
            raise ValueError(f"Invalid side: {side}")
        
        if strategy_type == "TREND":
            return self._trend_exit_plan(
                position_id, symbol, side, entry_price, atr, now_ms
            )
        
        elif strategy_type == "MEAN_REVERSION":
            return self._mean_reversion_exit_plan(
                position_id, symbol, side, entry_price, atr, now_ms
            )
        
        elif strategy_type == "BREAKOUT":
            return self._breakout_exit_plan(
                position_id, symbol, side, entry_price, atr, now_ms
            )
        
        else:
            raise ValueError(f"Unknown strategy type: {strategy_type}")
    
    def _trend_exit_plan(
        self,
        position_id: str,
        symbol: str,
        side: str,
        entry_price: float,
        atr: Optional[float],
        now_ms: int,
    ) -> ExitPlan:
        """
        Trend strategy: Wide SL (3× ATR), trailing stop, no fixed TP.
        """
        if not atr:
            raise ValueError("ATR required for TREND strategy")
        
        # Wide stop loss (3× ATR)
        if side == "LONG":
            stop_loss = entry_price - (3 * atr)
            activation_price = entry_price * 1.02  # 2% profit
        else:  # SHORT
            stop_loss = entry_price + (3 * atr)
            activation_price = entry_price * 0.98
        
        return ExitPlan(
            position_id=position_id,
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            stop_loss_price=stop_loss,
            take_profit_price=None,  # Let it run
            trailing_stop_activation_price=activation_price,
            trailing_stop_callback_pct=0.015,  # 1.5% callback
            max_duration_ms=None,
            created_at_ms=now_ms,
            last_updated_ms=now_ms,
            strategy_type="TREND",
        )
    
    def _mean_reversion_exit_plan(
        self,
        position_id: str,
        symbol: str,
        side: str,
        entry_price: float,
        atr: Optional[float],
        now_ms: int,
    ) -> ExitPlan:
        """
        Mean reversion: Tight SL (1.5× ATR), fixed TP (2× ATR), time limit.
        """
        if not atr:
            raise ValueError("ATR required for MEAN_REVERSION strategy")
        
        # Tight stop loss + fixed take profit
        if side == "LONG":
            stop_loss = entry_price - (1.5 * atr)
            take_profit = entry_price + (2 * atr)
        else:  # SHORT
            stop_loss = entry_price + (1.5 * atr)
            take_profit = entry_price - (2 * atr)
        
        return ExitPlan(
            position_id=position_id,
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            stop_loss_price=stop_loss,
            take_profit_price=take_profit,
            trailing_stop_activation_price=None,
            trailing_stop_callback_pct=None,
            max_duration_ms=3600000,  # 1 hour
            created_at_ms=now_ms,
            last_updated_ms=now_ms,
            strategy_type="MEAN_REVERSION",
        )
    
    def _breakout_exit_plan(
        self,
        position_id: str,
        symbol: str,
        side: str,
        entry_price: float,
        atr: Optional[float],
        now_ms: int,
    ) -> ExitPlan:
        """
        Breakout: Moderate SL (2× ATR), time-based exit if no follow-through.
        """
        if not atr:
            raise ValueError("ATR required for BREAKOUT strategy")
        
        # Moderate stop loss
        if side == "LONG":
            stop_loss = entry_price - (2 * atr)
        else:  # SHORT
            stop_loss = entry_price + (2 * atr)
        
        return ExitPlan(
            position_id=position_id,
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            stop_loss_price=stop_loss,
            take_profit_price=None,
            trailing_stop_activation_price=None,
            trailing_stop_callback_pct=None,
            max_duration_ms=1800000,  # 30 minutes
            created_at_ms=now_ms,
            last_updated_ms=now_ms,
            strategy_type="BREAKOUT",
        )
