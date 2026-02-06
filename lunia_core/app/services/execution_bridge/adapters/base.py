"""
Epoch C.1: Exchange Adapter — Base Contract

Defines the canonical interface for all exchange adapters.

CONTRACT RULES (NON-NEGOTIABLE):
1. Adapters MUST be stateless (no internal retry logic)
2. Adapters MUST return structured errors (ExecutionResult, no exceptions)
3. Adapters MUST NOT infer missing data
4. Adapters MUST generate deterministic clientOrderId from plan.id
5. Adapters have ZERO decision authority (execute plan as-is)
"""
from typing import Protocol, Dict
from ..models import OrderPlan, ExecutionResult


class ExchangeAdapter(Protocol):
    """
    Stateless exchange adapter interface.
    
    All exchange connectivity must implement this protocol.
    Guards (rate limit, retry) wrap adapters externally.
    
    Design Philosophy:
    - "Hands, not Brain" — Adapters execute, never decide
    - Fail-fast with structured errors
    - Deterministic behavior (same plan → same clientOrderId)
    """
    
    name: str  # Adapter identifier (e.g., "binance_sandbox", "binance_live")
    
    def place_order(self, plan: OrderPlan, reference_price: float) -> ExecutionResult:
        """
        Place order on exchange.
        
        Args:
            plan: Fully specified order plan from Council-approved verdict
            reference_price: Reference price for execution (from market data)
            
        Returns:
            ExecutionResult with:
            - executed=True + exchange_order_id (success)
            - executed=False + error_code (failure)
            
        Error Codes (Standardized):
        - RATE_LIMIT: Exchange rate limit hit
        - INSUFFICIENT_FUNDS: Insufficient balance
        - INVALID_SYMBOL: Symbol not found
        - INVALID_QUANTITY: Quantity below minimum
        - NETWORK_ERROR: Network/timeout error
        - UNKNOWN: Unclassified error
        
        MUST NOT raise exceptions (return ExecutionResult with error_code).
        """
        ...
    
    def cancel_order(self, exchange_order_id: str) -> bool:
        """
        Cancel order by exchange order ID.
        
        Args:
            exchange_order_id: Exchange's native order ID
            
        Returns:
            True if cancelled, False otherwise
        """
        ...
    
    def get_order_status(self, exchange_order_id: str) -> Dict:
        """
        Query order status (for reconciliation).
        
        Args:
            exchange_order_id: Exchange's native order ID
            
        Returns:
            Dict with:
            {
                "status": "NEW" | "FILLED" | "PARTIALLY_FILLED" | "CANCELLED" | "REJECTED",
                "filled_qty": float,
                "avg_price": float | None
            }
        """
        ...
