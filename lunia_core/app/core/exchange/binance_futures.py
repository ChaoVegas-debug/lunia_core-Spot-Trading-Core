"""Binance Futures exchange client with mock and testnet support."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

from app.compat.requests import requests

from .base import IExchange

logger = logging.getLogger(__name__)

MOCK_PRICES: Dict[str, float] = {
    "BTCUSDT": 31000.0,
    "ETHUSDT": 2100.0,
}


class BinanceFuturesError(RuntimeError):
    """Raised for Binance Futures related failures."""


@dataclass
class BinanceFutures(IExchange):
    """Client for interacting with Binance Futures Testnet with mock fallback."""

    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    use_testnet: bool = True
    mock: bool = False
    session: requests.Session = field(default_factory=requests.Session)

    def __post_init__(self) -> None:
        self.base_url = "https://testnet.binancefuture.com"
        self.timeout = 10
        self.retries = 3
        if not self.use_testnet:
            self.mock = True
            logger.info("BinanceFutures testnet disabled; using mock mode")
        elif not self.api_key or not self.api_secret:
            self.mock = True
            logger.warning("Missing Binance Futures credentials; falling back to mock mode")
        elif self.mock:
            logger.info("BinanceFutures forced into mock mode")
        else:
            logger.info("BinanceFutures initialized for testnet API calls")

    # Helpers -----------------------------------------------------------------
    def _build_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-MBX-APIKEY"] = self.api_key
        return headers

    def _mock_price(self, symbol: str) -> float:
        price = MOCK_PRICES.get(symbol.upper(), 1.0)
        logger.info("Returning mock futures price %.2f for %s", price, symbol)
        return price

    def _mock_response(self, data: Dict[str, object]) -> Dict[str, object]:
        logger.debug("Mock response generated: %s", data)
        return data

    def _handle_response(self, response: requests.Response) -> Dict[str, object]:
        try:
            response.raise_for_status()
        except requests.RequestException as exc:  # pragma: no cover - network path
            logger.error("Binance Futures request failed: %s", exc)
            raise BinanceFuturesError(str(exc)) from exc
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:  # pragma: no cover - invalid payload
            raise BinanceFuturesError("invalid-json") from exc
        logger.debug("Binance Futures response: %s", payload)
        return payload

    def _signed_params(self, params: Dict[str, object]) -> Optional[Dict[str, object]]:
        if not self.api_secret:
            logger.warning("Missing API secret; cannot sign futures request")
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
    ) -> Dict[str, object]:
        if self.mock:
            raise BinanceFuturesError("mock-mode")
        if signed and (not self.api_key or not self.api_secret):
            raise BinanceFuturesError("credentials-missing")

        params = params or {}
        request_params = params
        if signed:
            params_with_ts = dict(params)
            params_with_ts.setdefault("timestamp", int(time.time() * 1000))
            signed_params = self._signed_params(params_with_ts)
            if signed_params is None:
                raise BinanceFuturesError("signing-failed")
            request_params = signed_params

        url = f"{self.base_url}{path}"
        headers = self._build_headers()
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.retries + 1):
            try:
                if method.upper() == "GET":
                    resp = self.session.get(url, params=request_params, headers=headers, timeout=self.timeout)
                elif method.upper() == "POST":
                    resp = self.session.post(url, params=request_params, headers=headers, timeout=self.timeout)
                elif method.upper() == "DELETE":
                    resp = self.session.delete(url, params=request_params, headers=headers, timeout=self.timeout)
                else:
                    raise ValueError(f"Unsupported method {method}")
                return self._handle_response(resp)
            except (requests.RequestException, BinanceFuturesError) as exc:
                last_exc = exc
                logger.warning(
                    "Binance Futures %s %s failed on attempt %s/%s: %s",
                    method,
                    path,
                    attempt,
                    self.retries,
                    exc,
                )
                time.sleep(0.5)
        raise BinanceFuturesError(str(last_exc))

    def _validate_side(self, side: str) -> str:
        side_upper = side.upper()
        if side_upper not in {"BUY", "SELL"}:
            raise BinanceFuturesError("invalid-side")
        return side_upper

    # Public API ---------------------------------------------------------------
    def get_price(self, symbol: str) -> float:
        logger.info("Fetching futures price for %s", symbol)
        if self.mock:
            return self._mock_price(symbol)
        try:
            payload = self._request("GET", "/fapi/v1/ticker/price", {"symbol": symbol.upper()})
            return float(payload["price"])
        except (BinanceFuturesError, ValueError) as exc:  # pragma: no cover - network issues
            logger.warning("Futures price request failed (%s); switching to mock", exc)
            self.mock = True
            return self._mock_price(symbol)

    def set_leverage(self, symbol: str, leverage: int) -> Dict[str, object]:
        logger.info("Setting leverage=%s for %s", leverage, symbol)
        if self.mock:
            return self._mock_response({"symbol": symbol.upper(), "leverage": leverage, "status": "MOCK"})
        try:
            return self._request(
                "POST",
                "/fapi/v1/leverage",
                {"symbol": symbol.upper(), "leverage": leverage},
                signed=True,
            )
        except BinanceFuturesError as exc:  # pragma: no cover - network issues
            logger.warning("Leverage set failed (%s); using mock", exc)
            self.mock = True
            return self.set_leverage(symbol, leverage)

    def place_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        type: str = "MARKET",
    ) -> Dict[str, object]:
        side_upper = self._validate_side(side)
        logger.info("Placing futures %s order symbol=%s qty=%.8f", side_upper, symbol, qty)
        if self.mock:
            price = self._mock_price(symbol)
            order_id = f"futures-mock-{int(time.time() * 1000)}"
            return self._mock_response(
                {
                    "symbol": symbol.upper(),
                    "orderId": order_id,
                    "status": "FILLED",
                    "type": type,
                    "side": side_upper,
                    "avgPrice": price,
                    "executedQty": qty,
                    "cumQuote": price * qty,
                }
            )

        if not self.api_key or not self.api_secret:
            logger.warning("Missing credentials; falling back to mock order")
            self.mock = True
            return self.place_order(symbol, side_upper, qty, type)

        try:
            payload = self._request(
                "POST",
                "/fapi/v1/order",
                {
                    "symbol": symbol.upper(),
                    "side": side_upper,
                    "type": type,
                    "quantity": qty,
                },
                signed=True,
            )
            return payload
        except BinanceFuturesError as exc:  # pragma: no cover - network issues
            logger.warning("Futures order placement failed (%s); using mock", exc)
            self.mock = True
            return self.place_order(symbol, side_upper, qty, type)

    def cancel_order(self, order_id: str, symbol: str | None = None) -> Dict[str, object]:
        logger.info("Cancelling futures order %s", order_id)
        symbol_upper = symbol.upper() if symbol else "BTCUSDT"
        if self.mock:
            return self._mock_response({"orderId": order_id, "symbol": symbol_upper, "status": "CANCELED"})

        if not self.api_key or not self.api_secret:
            logger.warning("Missing credentials; falling back to mock cancel")
            self.mock = True
            return self.cancel_order(order_id, symbol_upper)

        try:
            return self._request(
                "DELETE",
                "/fapi/v1/order",
                {"symbol": symbol_upper, "orderId": order_id},
                signed=True,
            )
        except BinanceFuturesError as exc:  # pragma: no cover - network issues
            logger.warning("Futures cancel failed (%s); using mock", exc)
            self.mock = True
            return self.cancel_order(order_id, symbol_upper)

    def get_position(self, symbol: str) -> Optional[Dict[str, object]]:
        logger.info("Fetching futures position for %s", symbol)
        if self.mock:
            return self._mock_response(
                {
                    "symbol": symbol.upper(),
                    "positionAmt": 0.0,
                    "entryPrice": self._mock_price(symbol),
                }
            )

        try:
            positions = self._request("GET", "/fapi/v2/positionRisk", {"symbol": symbol.upper()}, signed=True)
        except BinanceFuturesError as exc:  # pragma: no cover - network issues
            logger.warning("Futures position request failed (%s); using mock", exc)
            self.mock = True
            return self.get_position(symbol)

        if isinstance(positions, list):
            for position in positions:
                if position.get("symbol") == symbol.upper():
                    return position
        return None

    def get_balance(self, asset: str = "USDT") -> Dict[str, object]:
        logger.info("Fetching futures balance for %s", asset)
        if self.mock:
            return self._mock_response({"asset": asset, "balance": 1000.0, "availableBalance": 1000.0})

        try:
            balances = self._request("GET", "/fapi/v2/balance", {}, signed=True)
        except BinanceFuturesError as exc:  # pragma: no cover - network issues
            logger.warning("Futures balance request failed (%s); using mock", exc)
            self.mock = True
            return self.get_balance(asset)

        if isinstance(balances, list):
            for balance in balances:
                if balance.get("asset") == asset:
                    return balance
        return {"asset": asset, "balance": 0.0, "availableBalance": 0.0}
