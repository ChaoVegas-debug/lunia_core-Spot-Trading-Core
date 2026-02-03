"""Shadow Simulator (PHASE 1 - Projection Layer)

Computes projected equity from snapshot + intent WITHOUT mutating real objects.

Constitution:
- Stateless between calls
- Deep-copy snapshot (no mutation)
- Decimal math only
- No imports of execution/exchange/order builder
"""
from decimal import Decimal
from typing import Dict, Any
from copy import deepcopy


class ShadowSimulator:
    """Projection layer for risk assessment (no side effects).
    
    PHASE 1 SHADOW MODE:
    - Projects impact of pending trade on equity
    - Stateless computation (no internal state)
    - Never mut ates input objects
    - Decimal math only
    """
    
    @staticmethod
    def project_impact(
        portfolio_snapshot: Dict[str, Any],
        trade_intent: Dict[str, Any],
        price: Decimal
    ) -> Dict[str, Decimal]:
        """Project equity impact of trade without executing it.
        
        Args:
            portfolio_snapshot: {cash: Decimal, position_qty: Decimal}
            trade_intent: {id: str, side: str, qty: Decimal}
            price: Current price (Decimal)
            
        Returns:
            {cash: Decimal, position_qty: Decimal, equity: Decimal}
            
        Raises:
            TypeError: If inputs are not Decimal
            ValueError: If unknown side
        """
        # Validate Decimal types
        if not isinstance(price, Decimal):
            raise TypeError(f"price must be Decimal, got {type(price)}")
        if not isinstance(portfolio_snapshot.get('cash'), Decimal):
            raise TypeError(f"portfolio_snapshot['cash'] must be Decimal")
        if not isinstance(portfolio_snapshot.get('position_qty'), Decimal):
            raise TypeError(f"portfolio_snapshot['position_qty'] must be Decimal")
        if not isinstance(trade_intent.get('qty'), Decimal):
            raise TypeError(f"trade_intent['qty'] must be Decimal")
        
        # Deep copy to avoid mutation (defensive)
        snapshot = deepcopy(portfolio_snapshot)
        
        # Extract values
        cash = snapshot['cash']
        position_qty = snapshot['position_qty']
        side = trade_intent['side']
        qty = trade_intent['qty']
        
        # Project impact
        if side == "BUY":
            # BUY: spend cash, gain position
            notional = qty * price
            projected_cash = cash - notional
            projected_position = position_qty + qty
            
        elif side == "SELL":
            # SELL: gain cash, lose position
            notional = qty * price
            projected_cash = cash + notional
            projected_position = position_qty - qty
            
        else:
            raise ValueError(f"Unknown side: {side}. Must be BUY or SELL.")
        
        # Compute projected equity
        projected_equity = projected_cash + (projected_position * price)
        
        # Return projection
        return {
            'cash': projected_cash,
            'position_qty': projected_position,
            'equity': projected_equity,
        }
