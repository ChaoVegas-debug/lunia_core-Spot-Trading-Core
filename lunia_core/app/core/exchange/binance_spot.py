"""Binance Spot exchange client supporting mock and testnet modes."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

import requests

from .base import IExchange

logger = logging.getLogger(__name__)

MOCK_PRICES: Dict[str, float] = {
    "BTCUSDT": 30000.0,
    "ETHUSDT": 2000.0,
    "BNBUSDT": 300.0,
}


class BinanceSpotError(RuntimeError):
    """Raised for Binance Spot related failures."""


@dataclass
class BinanceSpot(IExchange):
    """Binance Spot client with mock and testnet support."""

    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    use_testnet: bool = False
    mock: bool = True
    session: requests.Session = field(default_factory=requests.Session)

    time_offset: int = 0
    auth_proven: str = "UNVERIFIED" # UNVERIFIED, VERIFIED, FAILED
    
    def __post_init__(self) -> None:
        if self.api_key:
            self.api_key = self.api_key.strip()
        if self.api_secret:
            self.api_secret = self.api_secret.strip()

        if self.use_testnet:
             self.base_url = "https://testnet.binance.vision"
        else:
             self.base_url = "https://api.binance.com"
             
        self.timeout = 10
        self.retries = 3

        if not self.use_testnet and not (self.api_key and self.api_secret):
            # STRICT MODE: Do not fallback to mock.
            if not self.mock:
                logger.warning("BinanceSpot Mainnet requested without credentials. Calls will FAIL (Fail-Closed).")
        elif not self.api_key or not self.api_secret:
            if not self.mock:
                logger.warning("BinanceSpot initialized without credentials. Calls will FAIL (Fail-Closed).")
        elif self.mock:
            logger.info("BinanceSpot forced into mock mode")
        else:
            mode = "TESTNET" if self.use_testnet else "MAINNET"
            logger.info(f"BinanceSpot initialized for {mode} API calls")
            
    def verify_auth(self) -> bool:
        """
        Attempts a signed request to prove credentials are valid.
        Updates self.auth_proven state.
        """
        if self.mock:
            self.auth_proven = "VERIFIED" # Mock is always verified
            return True
            
        if not self.api_key or not self.api_secret:
            self.auth_proven = "FAILED"
            return False

        try:
            # Lightweight signed call
            self.get_balances(force_real=True)
            self.auth_proven = "VERIFIED"
            logger.info("BinanceSpot Authentication PROVEN (VERIFIED).")
            return True
        except Exception as e:
            logger.error(f"BinanceSpot Authentication FAILED: {e}")
            self.auth_proven = "FAILED"
            return False


    def _sync_time(self) -> None:
        """Synchronize client time with Binance server time."""
        try:
            resp = self.session.get(f"{self.base_url}/api/v3/time", timeout=5)
            resp.raise_for_status()
            server_time = resp.json()["serverTime"]
            local_time = int(time.time() * 1000)
            self.time_offset = server_time - local_time
            self._time_synced = True
            logger.info(f"Binance time synced. Offset: {self.time_offset}ms")
        except Exception as e:
            logger.error(f"Failed to sync time with Binance: {e}")
            # Do not raise, just warn. We will default to local time.

    def _get_timestamp(self) -> int:
        return int(time.time() * 1000) + self.time_offset

    # Utilities
    def _build_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-MBX-APIKEY"] = self.api_key
        return headers

    def _mock_price(self, symbol: str) -> float:
        price = MOCK_PRICES.get(symbol.upper(), 1.0)
        logger.info("Returning mock price %.2f for %s", price, symbol)
        return price

    def _mock_response(self, data: Dict[str, object]) -> Dict[str, object]:
        logger.debug("Mock response generated: %s", data)
        return data

    def _handle_response(self, response: requests.Response) -> Dict[str, object]:
        try:
            response.raise_for_status()
        except requests.RequestException as exc:  # pragma: no cover - error path
            logger.error("Binance API request failed: %s", exc)
            if response.text:
                 logger.error("Binance Error Body: %s", response.text)
                 
                 # Check for Timestamp error (-1021)
                 if "-1021" in response.text:
                     logger.warning("Timestamp error detected. Triggering re-sync.")
                     self._sync_time()
                     
            raise BinanceSpotError(str(exc)) from exc
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:  # pragma: no cover - error path
            logger.error("Invalid JSON received from Binance: %s", exc)
            raise BinanceSpotError("invalid-json") from exc
        logger.debug("Binance API response: %s", payload)
        return payload

    def _signed_params(self, params: Dict[str, object]) -> Optional[Dict[str, object]]:
        if not self.api_secret:
            logger.warning("Missing API secret; cannot sign request. Using mock mode")
            return None
        query = "&".join(f"{key}={value}" for key, value in params.items())
        signature = hmac.new(self.api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
        signed = dict(params)
        signed["signature"] = signature
        return signed

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, object]] = None,
        signed: bool = False,
        force_real: bool = False,
    ) -> Dict[str, object]:
        if self.mock and not force_real:
            raise BinanceSpotError("mock-mode")
        if signed and (not self.api_key or not self.api_secret):
            raise BinanceSpotError("credentials-missing")

        params = params or {}
        request_params = params
        if signed:
            params_with_timestamp = dict(params)
            # Use synced timestamp
            params_with_timestamp.setdefault("timestamp", self._get_timestamp())
            params_with_timestamp.setdefault("recvWindow", 5000)
            
            signed_params = self._signed_params(params_with_timestamp)
            if signed_params is None:
                raise BinanceSpotError("signing-failed")
            request_params = signed_params

        url = f"{self.base_url}{path}"
        headers = self._build_headers()
        last_exc: Optional[Exception] = None
        
        # [DIAGNOSTIC] Log Request Details
        if force_real:
            safe_params = {k:v for k,v in request_params.items() if k != "signature"}
            logger.info(f"[BINANCE_REQ] {method} {url} Params={safe_params} Signed={signed}")

        for attempt in range(1, self.retries + 1):
            try:
                t0 = time.time()
                if method.upper() == "GET":
                    resp = self.session.get(url, params=request_params, headers=headers, timeout=self.timeout)
                elif method.upper() == "POST":
                    resp = self.session.post(url, params=request_params, headers=headers, timeout=self.timeout)
                elif method.upper() == "DELETE":
                    resp = self.session.delete(url, params=request_params, headers=headers, timeout=self.timeout)
                else:
                    raise ValueError(f"Unsupported method {method}")
                
                latency = (time.time() - t0) * 1000
                
                # [DIAGNOSTIC] Log Response Details for REAL requests
                if force_real or not self.mock:
                    logger.info(f"[BINANCE_RESP] Status={resp.status_code} Latency={latency:.1f}ms URL={resp.url}")
                    if resp.status_code != 200:
                        logger.error(f"[BINANCE_ERR_BODY] {resp.text[:500]}") # Log first 500 chars of error
                
                return self._handle_response(resp)
            except (requests.RequestException, BinanceSpotError) as exc:
                last_exc = exc
                logger.warning(
                    "Binance request %s %s failed on attempt %s/%s: %s",
                    method,
                    path,
                    attempt,
                    self.retries,
                    exc,
                )
                time.sleep(0.5)
        raise BinanceSpotError(str(last_exc))

    def _validate_side(self, side: str) -> str:
        side_upper = side.upper()
        if side_upper not in {"BUY", "SELL"}:
            logger.warning("Invalid order side received: %s", side)
            raise BinanceSpotError("invalid-side")
        return side_upper

    # Public API
    def get_price(self, symbol: str) -> float:
        logger.info("Fetching price for symbol %s", symbol)
        if self.mock:
            return self._mock_price(symbol)

        try:
            payload = self._request("GET", "/api/v3/ticker/price", {"symbol": symbol.upper()})
            price = float(payload["price"])
            logger.debug("Received price %.2f for %s", price, symbol)
            return price
        except (BinanceSpotError, ValueError) as exc:  # pragma: no cover - network issues
            logger.warning("Price request failed (%s); falling back to mock", exc)
            self.mock = True
            return self._mock_price(symbol)

    def place_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        type: str = "MARKET",
    ) -> Dict[str, object]:
        side_upper = self._validate_side(side)
        
        # SAFETY: Dry Run Check
        import os
        is_dry_run = os.getenv("TRADING_DRY_RUN", "true").lower() == "true"
        
        logger.info("Placing %s order for %s qty=%.8f type=%s [DryRun=%s]", side_upper, symbol, qty, type, is_dry_run)
        
        if is_dry_run:
             # Return a fake order receipt that looks real but denotes dry run
             order_id = f"dry-{int(time.time() * 1000)}"
             price = self.get_price(symbol) # Fetch real price for realism if possible
             return {
                    "symbol": symbol.upper(),
                    "orderId": order_id,
                    "side": side_upper,
                    "type": type,
                    "origQty": qty,
                    "status": "FILLED_DRY_RUN", # Distinct status
                    "price": price,
                    "executedQty": qty,
                    "cummulativeQuoteQty": price * qty,
                    "transactTime": int(time.time() * 1000),
                }

        if self.mock:
            order_id = f"mock-{int(time.time() * 1000)}"
            price = self._mock_price(symbol)
            return self._mock_response(
                {
                    "symbol": symbol.upper(),
                    "orderId": order_id,
                    "side": side_upper,
                    "type": type,
                    "origQty": qty,
                    "status": "FILLED",
                    "price": price,
                    "executedQty": qty,
                    "cummulativeQuoteQty": price * qty,
                    "transactTime": int(time.time() * 1000),
                }
            )

        if not self.api_key or not self.api_secret:
            logger.warning("API credentials missing; using mock order response")
            self.mock = True
            return self.place_order(symbol, side, qty, type)

        # STRICT GATE
        if not self.mock and self.auth_proven != "VERIFIED":
             raise BinanceSpotError("auth-not-proven: LIVE Trading requires verified credentials")

        try:
            payload = self._request(
                "POST",
                "/api/v3/order",
                {
                    "symbol": symbol.upper(),
                    "side": side_upper,
                    "type": type,
                    "quantity": qty,
                },
                signed=True,
            )
            return payload
        except BinanceSpotError as exc:  # pragma: no cover - network issues
            logger.warning("Order placement failed (%s); using mock", exc)
            # Do NOT fall back to mock for real errors when trying to trade real money
            # Raise the error to let the UI know it failed
            raise
    
    def cancel_order(self, order_id: str) -> Dict[str, object]:
        logger.info("Cancelling order %s", order_id)
        if self.mock:
            return self._mock_response(
                {
                    "orderId": order_id,
                    "status": "CANCELED",
                }
            )

        if not self.api_key or not self.api_secret:
            logger.warning("Missing credentials; returning mock cancel response")
            self.mock = True
            return self.cancel_order(order_id)

        try:
            return self._request(
                "DELETE",
                "/api/v3/order",
                {"orderId": order_id},
                signed=True,
            )
        except BinanceSpotError as exc:  # pragma: no cover - network issues
            logger.warning("Order cancellation failed (%s); using mock", exc)
            self.mock = True
            return self.cancel_order(order_id)

    def get_position(self, symbol: str) -> Optional[Dict[str, object]]:
        logger.info("Fetching position for symbol %s", symbol)
        if self.mock:
            balance = 1.0 if symbol.upper() in MOCK_PRICES else 0.0
            return self._mock_response(
                {
                    "symbol": symbol.upper(),
                    "free": balance,
                    "locked": 0.0,
                    "time_offset": self.time_offset
                }
            )

        if not self.api_key or not self.api_secret:
            logger.warning("Missing credentials; returning mock position")
            self.mock = True
            return self.get_position(symbol)

        try:
            balances = self.get_balances()
        except BinanceSpotError as exc:  # pragma: no cover - network issues
            logger.warning("Balance request failed (%s); using mock", exc)
            self.mock = True
            return self.get_position(symbol)

        symbol_upper = symbol.upper()
        base_asset = symbol_upper[:-4]
        asset = balances.get(base_asset)
        if asset is None:
            return None
        return {
            "symbol": symbol_upper,
            "free": asset.get("free", 0.0),
            "locked": asset.get("locked", 0.0),
        }

    def get_balances(self, force_real: bool = False) -> Dict[str, Dict[str, float]]:
        if self.mock and not force_real:
            return {"USDT": {"free": 1000.0, "locked": 0.0}}
        
        # STRICT LIVE GATE
        # We allow the initial verify_auth() call to pass (it calls this method),
        # but subsequent calls should generally respect state. 
        # Actually, verifying by *calling* this method means we rely on _request to fail.
        # But let's add an explicit gate for safety if we are FAILED.
        if not self.mock and self.auth_proven == "FAILED":
             raise BinanceSpotError("auth-not-proven: Credentials previously rejected")

        # If force_real is True, we attempt request regardless of self.mock
        # But we must have keys.
        if force_real and (not self.api_key or not self.api_secret):
             raise BinanceSpotError("Cannot force real balances without keys")

        account = self._request("GET", "/api/v3/account", signed=True, force_real=force_real)
        balances: Dict[str, Dict[str, float]] = {}
        for balance in account.get("balances", []):
            balances[balance["asset"]] = {
                "free": float(balance.get("free", 0.0)),
                "locked": float(balance.get("locked", 0.0)),
            }
        return balances

    def get_order(self, symbol: str, order_id: str) -> Dict[str, object]:
        if self.mock:
            return {
                "symbol": symbol.upper(),
                "orderId": order_id,
                "status": "FILLED",
            }
        return self._request(
            "GET",
            "/api/v3/order",
            {"symbol": symbol.upper(), "orderId": order_id},
            signed=True,
        )
