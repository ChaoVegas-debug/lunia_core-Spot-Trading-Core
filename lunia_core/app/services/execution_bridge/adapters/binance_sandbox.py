"""
Epoch C.1: Binance Sandbox Adapter

Reference implementation using Binance Spot TESTNET.

CONSTRAINTS:
- Testnet endpoints only (https://testnet.binance.vision)
- Market orders ONLY (no limit orders in v1)
- Spot trading ONLY (no margin/futures)
- NO smart routing, NO slippage protection beyond basics

ERROR MAPPING (Binance → Internal):
- -1003 (TOO_MANY_REQUESTS) → RATE_LIMIT
- -1013 (INSUFFICIENT_BALANCE) → INSUFFICIENT_FUNDS
- -2010 (UNKNOWN_ORDER) → UNKNOWN_ORDER
- -1121 (INVALID_SYMBOL) → INVALID_SYMBOL
- -1111 (PRECISION_OVER_MAX) → INVALID_QUANTITY
- Network/Timeout → NETWORK_ERROR
"""
import hashlib
import logging
from typing import Dict, Optional
import requests

from ..models import OrderPlan, ExecutionResult, OrderSide

logger = logging.getLogger(__name__)


class BinanceSandboxAdapter:
    """
    Binance Spot Testnet adapter.
    
    TESTNET ONLY - Uses fake USDT balance.
    """
    
    name = "binance_sandbox"
    
    # Binance Testnet endpoints
    BASE_URL = "https://testnet.binance.vision"
    API_ENDPOINT = f"{BASE_URL}/api/v3"
    
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """
        Initialize adapter.
        
        Args:
            api_key: Binance testnet API key (optional for public endpoints)
            api_secret: Binance testnet API secret (optional for public endpoints)
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.session = requests.Session()
        self.session.headers.update({
            "X-MBX-APIKEY": api_key or "",
            "Content-Type": "application/json"
        })
    
    def _generate_client_order_id(self, plan_id: str) -> str:
        """
        Generate deterministic clientOrderId from plan_id.
        
        DETERMINISM: Same plan_id → Same clientOrderId
        Format: First 16 chars of SHA256(plan_id)
        """
        hash_obj = hashlib.sha256(plan_id.encode('utf-8'))
        return hash_obj.hexdigest()[:16].upper()
    
    def _map_error_code(self, binance_code: int, msg: str) -> str:
        """Map Binance error code to internal error taxonomy"""
        error_map = {
            -1003: "RATE_LIMIT",           # TOO_MANY_REQUESTS
            -1013: "INSUFFICIENT_FUNDS",   # Insufficient balance
            -2010: "UNKNOWN_ORDER",        # Order not found
            -1121: "INVALID_SYMBOL",       # Invalid symbol
            -1111: "INVALID_QUANTITY",     # Precision over max
            -1102: "INVALID_QUANTITY",     # Mandatory param empty/malformed
        }
        
        internal_code = error_map.get(binance_code, "UNKNOWN")
        
        logger.warning(
            f"Binance error mapped: code={binance_code} → {internal_code}, msg={msg}"
        )
        
        return internal_code
    
    def place_order(self, plan: OrderPlan, reference_price: float) -> ExecutionResult:
        """
        Place market order on Binance testnet.
        
        Returns ExecutionResult (never raises exception).
        """
        client_order_id = self._generate_client_order_id(plan.id)
        
        # Convert symbol format: BTC/USDT → BTCUSDT
        binance_symbol = plan.symbol.replace("/", "")
        
        # Build order payload
        payload = {
            "symbol": binance_symbol,
            "side": plan.side if isinstance(plan.side, str) else plan.side.value,  # BUY or SELL
            "type": "MARKET",
            "quantity": plan.quantity,
            "newClientOrderId": client_order_id,
        }
        
        logger.info(
            f"🚀 BINANCE SANDBOX: Placing {plan.side} {plan.quantity} {plan.symbol} "
            f"(clientOrderId={client_order_id})"
        )
        
        try:
            # POST to Binance testnet
            # Note: In production, this would require signature
            # For testnet without credentials, we'll simulate the response structure
            
            # SIMULATION MODE (if no API key)
            if not self.api_key:
                logger.warning(
                    "⚠️  No API key - SIMULATING Binance response (testnet sandbox mode)"
                )
                return ExecutionResult(
                    plan_id=plan.id,
                    verdict_id=plan.verdict_id,
                    executed=True,
                    exchange_order_id=f"SANDBOX-{client_order_id}",
                    filled_qty=plan.quantity,
                    avg_price=50000.0,  # Mock price
                    error_code=None,
                    error_detail=None
                )
            
            # REAL MODE (with API key) - would need signature implementation
            response = self.session.post(
                f"{self.API_ENDPOINT}/order",
                json=payload,
                timeout=5.0
            )
            
            if response.status_code == 200:
                data = response.json()
                
                return ExecutionResult(
                    plan_id=plan.id,
                    verdict_id=plan.verdict_id,
                    executed=True,
                    exchange_order_id=str(data.get("orderId")),
                    filled_qty=float(data.get("executedQty", 0)),
                    avg_price=float(data.get("price", 0)) if data.get("price") else None,
                    error_code=None,
                    error_detail=None
                )
            
            else:
                # Error response
                error_data = response.json()
                binance_code = error_data.get("code", -1)
                binance_msg = error_data.get("msg", "Unknown error")
                
                internal_code = self._map_error_code(binance_code, binance_msg)
                
                return ExecutionResult(
                    plan_id=plan.id,
                    verdict_id=plan.verdict_id,
                    executed=False,
                    exchange_order_id=None,
                    filled_qty=0.0,
                    avg_price=None,
                    error_code=internal_code,
                    error_detail=f"Binance {binance_code}: {binance_msg}"[:200]
                )
        
        except requests.exceptions.Timeout:
            logger.error("Binance request timeout")
            return ExecutionResult(
                plan_id=plan.id,
                verdict_id=plan.verdict_id,
                executed=False,
                exchange_order_id=None,
                filled_qty=0.0,
                avg_price=None,
                error_code="NETWORK_ERROR",
                error_detail="Request timeout"
            )
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Binance network error: {e}")
            return ExecutionResult(
                plan_id=plan.id,
                verdict_id=plan.verdict_id,
                executed=False,
                exchange_order_id=None,
                filled_qty=0.0,
                avg_price=None,
                error_code="NETWORK_ERROR",
                error_detail=str(e)[:200]
            )
        
        except Exception as e:
            # Catch-all safety net
            logger.error(f"Unexpected error in Binance adapter: {e}", exc_info=True)
            return ExecutionResult(
                plan_id=plan.id,
                verdict_id=plan.verdict_id,
                executed=False,
                exchange_order_id=None,
                filled_qty=0.0,
                avg_price=None,
                error_code="UNKNOWN",
                error_detail=str(e)[:200]
            )
    
    def cancel_order(self, exchange_order_id: str) -> bool:
        """Cancel order (not implemented in v1)"""
        logger.warning("cancel_order not implemented in Binance Sandbox v1")
        return False
    
    def get_order_status(self, exchange_order_id: str) -> Dict:
        """Get order status (not implemented in v1)"""
        logger.warning("get_order_status not implemented in Binance Sandbox v1")
        return {
            "status": "UNKNOWN",
            "filled_qty": 0.0,
            "avg_price": None
        }
