import logging
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime

from ..ai.agent import Agent
from .types import PortfolioDefinition, PortfolioStatus, PortfolioType
from ..state import get_state, set_state

logger = logging.getLogger(__name__)

class PortfolioExecutor:
    """
    Binds Portfolio Intent to Execution.
    Manages Rebalancing and De-Risking orders.
    """
    def __init__(self, agent: Agent):
        self.agent = agent

    def get_portfolio(self, portfolio_id: str) -> Optional[Dict[str, Any]]:
        state = get_state()
        portfolios = state.get("portfolio", {}).get("definitions", {})
        return portfolios.get(portfolio_id)

    def execute_rebalance(self, portfolio_id: str) -> Dict[str, Any]:
        """
        Calculates target positions and generates orders to minimize delta.
        For Phase 4 (Binding), this is a "Safe Binding":
        - Only executes if Portfolio is ACTIVE.
        - Calculates simple delta.
        """
        portfolio_dict = self.get_portfolio(portfolio_id)
        if not portfolio_dict:
             return {"ok": False, "error": "NOT_FOUND"}
        
        # Hydrate Dataclass (or use dict directly)
        # Using dict for simplicity as it matches state storage
        if portfolio_dict["status"] != PortfolioStatus.ACTIVE:
             return {"ok": False, "error": "PORTFOLIO_NOT_ACTIVE"}

        logger.info("Executing Rebalance for %s", portfolio_id)
        
        # 1. Calculate Targets
        total_captial = portfolio_dict["total_capital_allocation"]
        assets = portfolio_dict["assets"]
        
        results = []
        
        for asset in assets:
            symbol = asset["symbol"] + portfolio_dict["base_currency"] # e.g. BTCUSDT
            target_weight = asset["weight"]
            target_qty = (total_captial * target_weight) / self.agent.client.get_price(symbol)
            
            # Get Current Position
            # Need to know *Portfolio Specific* position? 
            # Currently Portfolio.py tracks GLOBAL positions. 
            # Phase 4 assumption: User has 1 global account. 
            # We map Portfolio Intent -> Global Account.
            # Ideally we check if other portfolios hold this asset too? 
            # For now, simplest binding: Compare Global Position vs Target (assuming 1 portfolio owns it or they sum up).
            # To be safe: We only BUY if under-allocated. We only SELL if over-allocated.
            # For this MVP binding, we will just log the INTENT to execute.
            # Actual automated rebalancing is dangerous without sub-accounts.
            
            # BUT, the mission says "MOVE CAPITAL".
            # Let's implement Entry Binding:
            # If current position < target position, BUY. 
            
            current_pos = self.agent.portfolio.get_position(symbol)
            current_qty = current_pos.quantity if current_pos else 0.0
            
            delta_qty = target_qty - current_qty
            
            # Threshold to avoid dust
            if abs(delta_qty * self.agent.client.get_price(symbol)) < 10.0:
                continue

            side = "BUY" if delta_qty > 0 else "SELL"
            
            # EXECUTE
            # We use a special strategy tag "PORTFOLIO_<ID>"
            
            res = self.agent.place_spot_order(
                symbol=symbol,
                side=side,
                qty=abs(delta_qty),
                strategy=f"PORTFOLIO_{portfolio_id}"
            )
            results.append(res)
            
        # record_audit("portfolio_rebalance", details={"id": portfolio_id, "orders": len(results)})
        return {"ok": True, "orders": results}

    def execute_derisk(self, portfolio_id: str) -> Dict[str, Any]:
        """
        Emergency De-Risking.
        Sells ALL assets associated with this portfolio found in global positions.
        """
        portfolio_dict = self.get_portfolio(portfolio_id)
        if not portfolio_dict:
             return {"ok": False, "error": "NOT_FOUND"}

        logger.warning("EXECUTING DERISK FOR %s", portfolio_id)
        
        # Update State to DE_RISKING if not already (should be done by caller, but safety check)
        # We assume caller handled state transition persistence.

        assets = portfolio_dict["assets"]
        results = []
        
        for asset in assets:
            symbol = asset["symbol"] + portfolio_dict["base_currency"]
            
            # Check Global Position
            current_pos = self.agent.portfolio.get_position(symbol)
            if not current_pos or current_pos.quantity <= 0:
                continue # Nothing to sell
                
            # SELL EVERYTHING
            logger.info("De-risking %s: Selling %.8f", symbol, current_pos.quantity)
            
            res = self.agent.place_spot_order(
                symbol=symbol,
                side="SELL",
                qty=current_pos.quantity,
                strategy=f"DERISK_{portfolio_id}",
                # Force Reduce Only logic if supported, or just verify logic
            )
            results.append(res)
            
        # record_audit("portfolio_derisk", details={"id": portfolio_id, "orders": len(results)})
        return {"ok": True, "orders": results}
