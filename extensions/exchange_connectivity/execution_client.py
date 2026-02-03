"""
PHASE 14B — LIVE ADAPTER: Execution Client (WRITE MODE)

Write-capable Binance client for order execution.

CRITICAL GOVERNANCE:
- Adapter has HANDS, not BRAIN
- No decision logic (only translation + normalization)
- Testnet default (mainnet requires explicit opt-in)
- No retries, no state machine
- Returns OrderResult only (never raw JSON)

DANGER: This module can sign and submit real orders.
MUST ONLY be called after Phase 14A approval.
"""

import urllib.parse
from decimal import Decimal
from typing import Optional, Literal, Dict, Any

from .binance_client import BinanceClient
from .trade_models import (
    OrderResult,
    OrderSide,
    OrderType,
    generate_client_order_id,
    parse_binance_order_response,
    parse_binance_error_to_order_result,
)
from .models import ErrorCode


# ────────────────────────────────────────────────────────────────────────────────
# EXECUTION CLIENT (WRITE-ENABLED)
# ────────────────────────────────────────────────────────────────────────────────

class BinanceExecutionClient(BinanceClient):
    """
    Write-enabled Binance client for order execution.
    
    GOVERNANCE RULES:
    - Testnet default (mainnet requires allow_mainnet=True)
    - No decision logic (only executes what it's told)
    - Returns OrderResult (normalized, deterministic)
    - No retries (single attempt only)
    - No state tracking (stateless)
    
    DANGER: Can submit real orders. Use with extreme caution.
    """
    
    # Extend allowed endpoints for write operations
    WRITE_ENDPOINTS = {
        "/api/v3/order",       # POST (create), DELETE (cancel), GET (query)
        "/api/v3/order/test",  # POST (test order, no execution)
    }
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        env: Optional[str] = None,
        base_url: Optional[str] = None,
        allow_mainnet: bool = False,
    ):
        """
        Initialize execution client.
        
        Args:
            api_key: API key (required for trading)
            api_secret: API secret (required for trading)
            env: Environment ("mainnet" | "testnet" | None)
            base_url: Custom base URL (overrides env)
            allow_mainnet: Explicit mainnet opt-in (default False)
        
        GOVERNANCE:
        - env=None → defaults to "testnet"
        - env="mainnet" requires allow_mainnet=True (fail-closed)
        """
        # TESTNET DEFAULT (safety first)
        if env is None and base_url is None:
            env = "testnet"
        
        # MAINNET GUARD (explicit opt-in required)
        if env == "mainnet" and not allow_mainnet:
            raise ValueError(
                "Mainnet trading requires explicit allow_mainnet=True flag. "
                "This is a safety gate to prevent accidental mainnet usage."
            )
        
        # Initialize parent (read-only client)
        super().__init__(
            api_key=api_key,
            api_secret=api_secret,
            env=env,
            base_url=base_url,
        )
        
        # Store extended allowlist (instance-level for override)
        from .binance_client import ALLOWED_ENDPOINTS
        self._allowed_endpoints_extended = ALLOWED_ENDPOINTS | self.WRITE_ENDPOINTS
    
    def _check_endpoint_allowed(self, path: str) -> Optional[Any]:
        """
        Override to allow write endpoints.
        
        Uses extended allowlist (read + write).
        """
        # Check extended allowlist
        if path not in self._allowed_endpoints_extended:
            return {
                "code": ErrorCode.FORBIDDEN_ENDPOINT,
                "message": f"Endpoint not in allowlist: {path}",
            }
        
        # No forbidden pattern check for /api/v3/order (controlled by allowlist)
        return None
    
    def create_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        client_order_id: Optional[str] = None,
        test_mode: bool = False,
    ) -> OrderResult:
        """
        Create order (WRITE OPERATION).
        
        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            side: "BUY" or "SELL"
            order_type: "MARKET" or "LIMIT"
            quantity: Order quantity (Decimal)
            price: Limit price (required for LIMIT, ignored for MARKET)
            client_order_id: Optional client order ID (auto-generated if None)
            test_mode: If True, use test endpoint (no real execution)
        
        Returns:
            OrderResult (normalized)
        
        GOVERNANCE:
        - No decision logic (executes exactly as told)
        - Single attempt (no retries)
        - Returns UNKNOWN on network ambiguity
        """
        if not self.auth_configured:
            return parse_binance_error_to_order_result(
                error_code="AUTH_REQUIRED",
                error_message="API credentials not configured",
                symbol=symbol,
                client_order_id=client_order_id,
            )
        
        # Get server time (required for signing)
        time_resp = self.server_time()
        if not time_resp["ok"]:
            return parse_binance_error_to_order_result(
                error_code=ErrorCode.TIMEOUT,
                error_message="Failed to get server time",
                symbol=symbol,
                client_order_id=client_order_id,
            )
        
        server_time_ms = time_resp["data"]["serverTime"]
        
        # Generate client_order_id if not provided (deterministic)
        if not client_order_id:
            client_order_id = generate_client_order_id(symbol, server_time_ms)
        
        # Build params
        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": str(quantity),  # Decimal → str for API
            "newClientOrderId": client_order_id,
        }
        
        # Add price for LIMIT orders
        if order_type == "LIMIT":
            if price is None:
                return parse_binance_error_to_order_result(
                    error_code="INVALID_PRICE",
                    error_message="Price required for LIMIT orders",
                    symbol=symbol,
                    client_order_id=client_order_id,
                )
            params["price"] = str(price)
            params["timeInForce"] = "GTC"  # Good-Til-Canceled
        
        # Choose endpoint (test or real)
        endpoint = "/api/v3/order/test" if test_mode else "/api/v3/order"
        
        # Execute request
        try:
            response = self._request(
                method="POST",
                path=endpoint,
                params=params,
                signed=True,
                server_time_ms=server_time_ms,
            )
            
            # Parse response
            return parse_binance_order_response(
                response=response,
                symbol=symbol,
                client_order_id=client_order_id,
            )
        
        except Exception as e:
            # Fail-safe: determine if REJECTED or UNKNOWN
            error_message = str(e)
            
            # Check if definitive rejection
            if "insufficient" in error_message.lower() or "balance" in error_message.lower():
                error_code = "INSUFFICIENT_BALANCE"
            elif "invalid" in error_message.lower():
                error_code = "INVALID_ORDER"
            elif "timeout" in error_message.lower() or "connection" in error_message.lower():
                error_code = ErrorCode.TIMEOUT
            else:
                error_code = ErrorCode.HTTP_ERROR
            
            return parse_binance_error_to_order_result(
                error_code=error_code,
                error_message=error_message,
                symbol=symbol,
                client_order_id=client_order_id,
            )
    
    def cancel_order(
        self,
        symbol: str,
        order_id: Optional[str] = None,
        client_order_id: Optional[str] = None,
    ) -> OrderResult:
        """
        Cancel order (WRITE OPERATION).
        
        Args:
            symbol: Trading pair
            order_id: Exchange order ID (optional if client_order_id provided)
            client_order_id: Client order ID (optional if order_id provided)
        
        Returns:
            OrderResult (normalized)
        
        GOVERNANCE:
        - No decision logic
        - Single attempt (no retries)
        """
        if not self.auth_configured:
            return parse_binance_error_to_order_result(
                error_code="AUTH_REQUIRED",
                error_message="API credentials not configured",
                symbol=symbol,
                client_order_id=client_order_id,
            )
        
        if not order_id and not client_order_id:
            return parse_binance_error_to_order_result(
                error_code="INVALID_ORDER",
                error_message="Either order_id or client_order_id required",
                symbol=symbol,
                client_order_id=client_order_id,
            )
        
        # Get server time
        time_resp = self.server_time()
        if not time_resp["ok"]:
            return parse_binance_error_to_order_result(
                error_code=ErrorCode.TIMEOUT,
                error_message="Failed to get server time",
                symbol=symbol,
                client_order_id=client_order_id,
            )
        
        server_time_ms = time_resp["data"]["serverTime"]
        
        # Build params
        params: Dict[str, Any] = {"symbol": symbol}
        if order_id:
            params["orderId"] = order_id
        if client_order_id:
            params["origClientOrderId"] = client_order_id
        
        # Execute request
        try:
            response = self._request(
                method="DELETE",
                path="/api/v3/order",
                params=params,
                signed=True,
                server_time_ms=server_time_ms,
            )
            
            return parse_binance_order_response(
                response=response,
                symbol=symbol,
                client_order_id=client_order_id,
            )
        
        except Exception as e:
            return parse_binance_error_to_order_result(
                error_code=ErrorCode.HTTP_ERROR,
                error_message=str(e),
                symbol=symbol,
                client_order_id=client_order_id,
            )
    
    def get_order_status(
        self,
        symbol: str,
        order_id: Optional[str] = None,
        client_order_id: Optional[str] = None,
    ) -> OrderResult:
        """
        Query order status (READ OPERATION, but signed).
        
        Args:
            symbol: Trading pair
            order_id: Exchange order ID (optional if client_order_id provided)
            client_order_id: Client order ID (optional if order_id provided)
        
        Returns:
            OrderResult (normalized)
        """
        if not self.auth_configured:
            return parse_binance_error_to_order_result(
                error_code="AUTH_REQUIRED",
                error_message="API credentials not configured",
                symbol=symbol,
                client_order_id=client_order_id,
            )
        
        if not order_id and not client_order_id:
            return parse_binance_error_to_order_result(
                error_code="INVALID_ORDER",
                error_message="Either order_id or client_order_id required",
                symbol=symbol,
                client_order_id=client_order_id,
            )
        
        # Get server time
        time_resp = self.server_time()
        if not time_resp["ok"]:
            return parse_binance_error_to_order_result(
                error_code=ErrorCode.TIMEOUT,
                error_message="Failed to get server time",
                symbol=symbol,
                client_order_id=client_order_id,
            )
        
        server_time_ms = time_resp["data"]["serverTime"]
        
        # Build params
        params: Dict[str, Any] = {"symbol": symbol}
        if order_id:
            params["orderId"] = order_id
        if client_order_id:
            params["origClientOrderId"] = client_order_id
        
        # Execute request
        try:
            response = self._request(
                method="GET",
                path="/api/v3/order",
                params=params,
                signed=True,
                server_time_ms=server_time_ms,
            )
            
            return parse_binance_order_response(
                response=response,
                symbol=symbol,
                client_order_id=client_order_id,
            )
        
        except Exception as e:
            return parse_binance_error_to_order_result(
                error_code=ErrorCode.HTTP_ERROR,
                error_message=str(e),
                symbol=symbol,
                client_order_id=client_order_id,
            )
