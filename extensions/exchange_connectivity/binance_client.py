"""
PHASE 12A — EXCHANGE CONNECTIVITY: Binance Client (READ-ONLY)

Production-safe, deterministic, read-only Binance REST client.

CRITICAL RULES:
- Read-only only (no trading endpoints)
- No wall-clock usage (serverTime from exchange)
- Fail-closed (never crash)
- Secrets redacted
- Endpoint allowlist enforced
"""

import os
import json
import hmac
import hashlib
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, Any, Optional

from .security import SafeSecret, redact_api_key, sanitize_error_message
from .models import ErrorCode, ErrorObject, Response


# Endpoint allowlist (MANDATORY - deny by default)
ALLOWED_ENDPOINTS = {
    "/api/v3/ping",
    "/api/v3/time",
    "/api/v3/exchangeInfo",
    "/api/v3/ticker/price",
    "/api/v3/depth",
    "/api/v3/account",  # Read-only signed
}

# Forbidden patterns (HARD BLOCK)
FORBIDDEN_PATTERNS = [
    "/order",
    "/fapi",
    "/dapi",
    "/sapi",
    "userDataStream",
    "listenKey",
]


class BinanceClient:
    """
    Read-only Binance REST client.
    
    Features:
    - Endpoint allowlist enforcement
    - HMAC signature for authenticated requests
    - Automatic secret redaction
    - Fail-closed error handling
    - No wall-clock usage
    """
    
    # Base URLs
    MAINNET_BASE_URL = "https://api.binance.com"
    TESTNET_BASE_URL = "https://testnet.binance.vision"
    
    # Timeouts (no wall-clock)
    CONNECT_TIMEOUT = 5  # seconds
    READ_TIMEOUT = 10  # seconds
    
    # HMAC window (no wall-clock comparisons)
    RECV_WINDOW = 5000  # milliseconds
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        env: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """
        Initialize Binance client.
        
        Args:
            api_key: API key (optional, for signed requests)
            api_secret: API secret (optional, for signed requests)
            env: Environment ("mainnet" | "testnet" | None)
            base_url: Custom base URL (overrides env)
        """
        self.api_key = SafeSecret(api_key)
        self.api_secret = SafeSecret(api_secret)
        self.env = env
        
        # Determine base URL
        if base_url:
            self.base_url = base_url
        elif env == "mainnet":
            self.base_url = self.MAINNET_BASE_URL
        elif env == "testnet":
            self.base_url = self.TESTNET_BASE_URL
        else:
            # Fail-closed: require explicit env
            self.base_url = None
        
        self.auth_configured = self.api_key.is_set() and self.api_secret.is_set()
    
    def _check_endpoint_allowed(self, path: str) -> Optional[ErrorObject]:
        """
        Check if endpoint is in allowlist.
        
        Args:
            path: Endpoint path (e.g., "/api/v3/ping")
        
        Returns:
            ErrorObject if forbidden, None if allowed
        """
        # Check allowlist
        if path not in ALLOWED_ENDPOINTS:
            return ErrorObject(
                code=ErrorCode.FORBIDDEN_ENDPOINT,
                message=f"Endpoint not in allowlist: {path}",
                details={"path": path}
            )
        
        # Check forbidden patterns
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in path:
                return ErrorObject(
                    code=ErrorCode.FORBIDDEN_ENDPOINT,
                    message=f"Forbidden pattern detected: {pattern}",
                    details={"path": path, "pattern": pattern}
                )
        
        return None
    
    def _sign_request(self, params: Dict[str, Any], server_time_ms: int) -> str:
        """
        Sign request with HMAC SHA256.
        
        Args:
            params: Query parameters
            server_time_ms: Server timestamp (from /api/v3/time)
        
        Returns:
            HMAC signature (hex)
        """
        if not self.api_secret.is_set():
            raise ValueError("API secret required for signing")
        
        # Add timestamp and recvWindow
        params_with_time = params.copy()
        params_with_time["timestamp"] = server_time_ms
        params_with_time["recvWindow"] = self.RECV_WINDOW
        
        # Build query string (sorted keys for determinism)
        query_string = urllib.parse.urlencode(sorted(params_with_time.items()))
        
        # HMAC SHA256
        signature = hmac.new(
            self.api_secret.get().encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False,
        server_time_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Execute HTTP request.
        
        Args:
            method: HTTP method ("GET", "POST", etc.)
            path: Endpoint path
            params: Query parameters
            signed: Whether to sign request
            server_time_ms: Server time for signing (required if signed=True)
        
        Returns:
            Parsed JSON response
        
        Raises:
            Exception: On any error (caller must handle)
        """
        if not self.base_url:
            raise ValueError("Base URL not configured (env required)")
        
        # Check endpoint allowlist
        error = self._check_endpoint_allowed(path)
        if error:
            raise ValueError(error.message)
        
        # Build URL
        url = f"{self.base_url}{path}"
        
        # Add params
        final_params = params.copy() if params else {}
        
        # Sign if needed
        if signed:
            if not self.auth_configured:
                raise ValueError("Auth required for signed endpoints")
            if server_time_ms is None:
                raise ValueError("server_time_ms required for signed requests")
            
            signature = self._sign_request(final_params, server_time_ms)
            final_params["signature"] = signature
        
        # Build query string
        if final_params:
            query_string = urllib.parse.urlencode(sorted(final_params.items()))
            url = f"{url}?{query_string}"
        
        # Build headers
        headers = {}
        if signed and self.api_key.is_set():
            headers["X-MBX-APIKEY"] = self.api_key.get()
        
        # Execute request
        req = urllib.request.Request(url, headers=headers, method=method)
        
        with urllib.request.urlopen(req, timeout=self.READ_TIMEOUT) as response:
            body = response.read().decode('utf-8')
            return json.loads(body)
    
    def _safe_request(
        self,
        method: str,
        path: str,
        endpoint_name: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False,
        server_time_ms: Optional[int] = None,
    ) -> Response:
        """
        Safe request wrapper (fail-closed).
        
        Args:
            method: HTTP method
            path: Endpoint path
            endpoint_name: Logical endpoint name (for response)
            params: Query parameters
            signed: Whether to sign
            server_time_ms: Server time (for signing)
        
        Returns:
            Response object (never throws)
        """
        try:
            data = self._request(method, path, params, signed, server_time_ms)
            return Response(
                ok=True,
                exchange="binance",
                endpoint=endpoint_name,
                data=data,
                error=None,
            )
        except urllib.error.HTTPError as e:
            # HTTP error
            try:
                body = e.read().decode('utf-8')
                error_data = json.loads(body)
                message = error_data.get('msg', str(e))
            except Exception:
                message = str(e)
            
            # Sanitize
            message = sanitize_error_message(
                message,
                self.api_key.get() if self.api_key.is_set() else None,
                self.api_secret.get() if self.api_secret.is_set() else None,
            )
            
            # Determine error code
            if e.code == 401:
                code = ErrorCode.AUTH_FAILED
            elif e.code == 429:
                code = ErrorCode.RATE_LIMIT
            else:
                code = ErrorCode.HTTP_ERROR
            
            return Response(
                ok=False,
                exchange="binance",
                endpoint=endpoint_name,
                data=None,
                error=ErrorObject(
                    code=code,
                    message=message,
                    details={"http_status": e.code}
                ),
            )
        
        except urllib.error.URLError as e:
            # Network error / timeout
            return Response(
                ok=False,
                exchange="binance",
                endpoint=endpoint_name,
                data=None,
                error=ErrorObject(
                    code=ErrorCode.TIMEOUT,
                    message=f"Network error: {str(e)}",
                ),
            )
        
        except json.JSONDecodeError as e:
            # JSON parse error
            return Response(
                ok=False,
                exchange="binance",
                endpoint=endpoint_name,
                data=None,
                error=ErrorObject(
                    code=ErrorCode.JSON_PARSE_ERROR,
                    message=f"Invalid JSON: {str(e)}",
                ),
            )
        
        except Exception as e:
            # Catch-all (fail-closed)
            message = sanitize_error_message(
                str(e),
                self.api_key.get() if self.api_key.is_set() else None,
                self.api_secret.get() if self.api_secret.is_set() else None,
            )
            
            return Response(
                ok=False,
                exchange="binance",
                endpoint=endpoint_name,
                data=None,
                error=ErrorObject(
                    code=ErrorCode.HTTP_ERROR,
                    message=message,
                ),
            )
    
    # ────────────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ────────────────────────────────────────────────────────────────────────
    
    def ping(self) -> Dict[str, Any]:
        """
        Test connectivity.
        
        Returns:
            Response dict with ok/error
        """
        return self._safe_request("GET", "/api/v3/ping", "ping").to_dict()
    
    def server_time(self) -> Dict[str, Any]:
        """
        Get server time.
        
        Returns:
            Response dict with {ok, data: {serverTime: int}}
        """
        return self._safe_request("GET", "/api/v3/time", "server_time").to_dict()
    
    def exchange_info(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Get exchange info.
        
        Args:
            symbol: Optional symbol filter
        
        Returns:
            Response dict with exchange metadata
        """
        params = {}
        if symbol:
            params["symbol"] = symbol
        
        resp = self._safe_request("GET", "/api/v3/exchangeInfo", "exchange_info", params)
        
        # Sort symbols deterministically if present
        if resp.ok and resp.data and "symbols" in resp.data:
            resp.data["symbols"] = sorted(resp.data["symbols"], key=lambda x: x.get("symbol", ""))
        
        return resp.to_dict()
    
    def ticker_price(self, symbol: str) -> Dict[str, Any]:
        """
        Get ticker price.
        
        Args:
            symbol: Symbol (e.g., "BTCUSDT")
        
        Returns:
            Response dict with {ok, data: {symbol, price}}
        """
        params = {"symbol": symbol}
        return self._safe_request("GET", "/api/v3/ticker/price", "ticker_price", params).to_dict()
    
    def depth(self, symbol: str, limit: int = 20) -> Dict[str, Any]:
        """
        Get order book depth.
        
        Args:
            symbol: Symbol (e.g., "BTCUSDT")
            limit: Depth limit (default 20)
        
        Returns:
            Response dict with {ok, data: {bids: [...], asks: [...]}}
        """
        params = {"symbol": symbol, "limit": limit}
        return self._safe_request("GET", "/api/v3/depth", "depth", params).to_dict()
    
    def account_readonly_summary(self) -> Dict[str, Any]:
        """
        Get redacted account summary (read-only signed endpoint).
        
        Returns:
            Response dict with redacted account info (NO balances)
        """
        if not self.auth_configured:
            return Response(
                ok=False,
                exchange="binance",
                endpoint="account_readonly_summary",
                data=None,
                error=ErrorObject(
                    code=ErrorCode.ENV_MISSING,
                    message="API credentials not configured",
                ),
            ).to_dict()
        
        # Get server time first
        time_resp = self.server_time()
        if not time_resp["ok"]:
            return Response(
                ok=False,
                exchange="binance",
                endpoint="account_readonly_summary",
                data=None,
                error=ErrorObject(
                    code=ErrorCode.AUTH_FAILED,
                    message="Failed to get server time for signing",
                    details=time_resp.get("error"),
                ),
            ).to_dict()
        
        server_time_ms = time_resp["data"]["serverTime"]
        
        # Get account (signed)
        resp = self._safe_request(
            "GET",
            "/api/v3/account",
            "account_readonly_summary",
            params={},
            signed=True,
            server_time_ms=server_time_ms,
        )
        
        # Redact: remove balances, keep metadata only
        if resp.ok and resp.data:
            summary = {
                "canTrade": resp.data.get("canTrade"),
                "canWithdraw": resp.data.get("canWithdraw"),
                "canDeposit": resp.data.get("canDeposit"),
                "accountType": resp.data.get("accountType"),
                "permissions": resp.data.get("permissions"),
                "balances_count": len(resp.data.get("balances", [])),
            }
            
            return Response(
                ok=True,
                exchange="binance",
                endpoint="account_readonly_summary",
                data=summary,
                error=None,
            ).to_dict()
        
        return resp.to_dict()


def build_binance_client_from_env() -> BinanceClient:
    """
    Build Binance client from environment variables.
    
    Env vars:
    - EXCHANGE_BINANCE_API_KEY (optional)
    - EXCHANGE_BINANCE_API_SECRET (optional)
    - EXCHANGE_BINANCE_ENV ("mainnet" | "testnet", optional but recommended)
    - EXCHANGE_BINANCE_REST_BASE_URL (optional override)
    
    Returns:
        BinanceClient (may have auth_configured=False)
    """
    api_key = os.getenv("EXCHANGE_BINANCE_API_KEY")
    api_secret = os.getenv("EXCHANGE_BINANCE_API_SECRET")
    env = os.getenv("EXCHANGE_BINANCE_ENV")
    base_url = os.getenv("EXCHANGE_BINANCE_REST_BASE_URL")
    
    return BinanceClient(
        api_key=api_key,
        api_secret=api_secret,
        env=env,
        base_url=base_url,
    )
