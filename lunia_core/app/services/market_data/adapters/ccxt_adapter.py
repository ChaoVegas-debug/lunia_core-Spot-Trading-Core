"""
EPOCH D: CCXT Exchange Adapter
Security-first, fail-closed, deterministic error semantics
"""
from __future__ import annotations

import logging
import os
import random
import time
from typing import Any, Dict, List, Optional

import ccxt

from ..interfaces import IExchangeAdapter
from ..models import (
    TickerSnapshot,
    Candle,
    OrderBookSnapshot,
    BalanceSnapshot,
    PriceLevel,
    SubmitOrderResult,
    OrderStatusResult
)
from ...execution.exceptions import HardError, SoftError

logger = logging.getLogger(__name__)


class CCXTAdapter(IExchangeAdapter):
    """
    CCXT-based exchange adapter
    
    Features:
    - Environment-only secret loading (never log)
    - Deterministic Hard/Soft error mapping
    - Bounded retry with backoff
    - Data normalization to strict models
    """
    
    # Retry configuration
    MAX_RETRY_ATTEMPTS = 3
    BASE_BACKOFF_SEC = 0.5
    MAX_BACKOFF_SEC = 5.0
    
    def __init__(
        self,
        exchange_id: Optional[str] = None,
        api_key: Optional[str] = None,
        secret: Optional[str] = None
    ):
        """
        Initialize CCXT adapter
        
        Args:
            exchange_id: Exchange ID (e.g., "binance", "bybit"). Defaults to LUNIA_EXCHANGE_ID env var.
            api_key: API key (optional override). Defaults to LUNIA_EXCHANGE_API_KEY env var.
            secret: API secret (optional override). Defaults to LUNIA_EXCHANGE_SECRET env var.
        
        Raises:
            ValueError: If required env vars missing
        """
        # Load from environment (fail-closed if missing)
        self.exchange_id = exchange_id or os.getenv("LUNIA_EXCHANGE_ID")
        self._api_key = api_key or os.getenv("LUNIA_EXCHANGE_API_KEY")
        self._secret = secret or os.getenv("LUNIA_EXCHANGE_SECRET")
        
        if not self.exchange_id:
            raise ValueError("LUNIA_EXCHANGE_ID environment variable required")
        
        # API key is optional for public endpoints, but required for trading/balance
        # We don't fail here, but will fail-closed when needed
        
        # Initialize CCXT exchange
        try:
            exchange_class = getattr(ccxt, self.exchange_id)
        except AttributeError:
            raise ValueError(f"Unknown exchange ID: {self.exchange_id}")
        
        self.exchange = exchange_class({
            'apiKey': self._api_key,
            'secret': self._secret,
            'enableRateLimit': True,  # CRITICAL: respect rate limits
            'options': {
                'defaultType': 'future',  # Can be overridden per method
            }
        })
        
        # Load markets (required for symbol validation)
        self._markets_loaded = False
        self._load_markets()
        
        logger.info(f"CCXTAdapter initialized: exchange={self.exchange_id}")
    
    def _load_markets(self):
        """Load and cache exchange markets"""
        if self._markets_loaded:
            return
        
        try:
            self.exchange.load_markets()
            self._markets_loaded = True
            logger.info(f"Loaded {len(self.exchange.markets)} markets from {self.exchange_id}")
        except Exception as e:
            # Fail-closed: Cannot proceed without markets
            raise HardError(f"Failed to load markets: {self._safe_error_message(e)}")
    
    def _safe_error_message(self, error: Exception) -> str:
        """
        Create safe error message (NEVER include secrets)
        
        Args:
            error: Original exception
        
        Returns:
            Sanitized error message
        """
        msg = str(error)
        
        # Remove API key/secret if accidentally included
        if self._api_key:
            msg = msg.replace(self._api_key, "***API_KEY***")
        if self._secret:
            msg = msg.replace(self._secret, "***SECRET***")
        
        return msg
    
    def _map_ccxt_exception(self, error: Exception) -> Exception:
        """
        Map CCXT exception to Epoch C Hard/Soft hierarchy
        
        Args:
            error: Original CCXT exception
        
        Returns:
            Mapped HardError or SoftError
        """
        safe_msg = self._safe_error_message(error)
        
        # Soft errors (ambiguous - retry safe)
        if isinstance(error, (ccxt.NetworkError, ccxt.RequestTimeout)):
            return SoftError(f"Network/timeout error: {safe_msg}")
        
        # Check for HTTP 502/503/504 in error message
        if any(code in str(error) for code in ["502", "503", "504"]):
            return SoftError(f"Upstream error: {safe_msg}")
        
        # Hard errors (definitive rejection - no retry)
        if isinstance(error, ccxt.AuthenticationError):
            return HardError(f"Authentication failed: {safe_msg}")
        
        if isinstance(error, ccxt.InsufficientFunds):
            return HardError(f"Insufficient funds: {safe_msg}")
        
        if isinstance(error, (ccxt.InvalidOrder, ccxt.BadRequest)):
            return HardError(f"Invalid order/request: {safe_msg}")
        
        # Order not found is also hard error (definitive)
        if "not found" in str(error).lower() or isinstance(error, ccxt.OrderNotFound):
            return HardError(f"Order not found: {safe_msg}")
        
        # Unknown errors default to SoftError (fail-closed ambiguous)
        logger.warning(f"Unknown CCXT error, defaulting to SoftError: {type(error).__name__}")
        return SoftError(f"Unknown exchange error: {safe_msg}")
    
    def _retry_with_backoff(self, func, *args, **kwargs):
        """
        Execute function with bounded retry and exponential backoff
        
        Only retries SoftErrors. HardErrors are raised immediately.
        
        Args:
            func: Function to execute
            *args, **kwargs: Function arguments
        
        Returns:
            Function result
        
        Raises:
            HardError: On definitive failures
            SoftError: After max retry attempts exhausted
        """
        for attempt in range(self.MAX_RETRY_ATTEMPTS):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                mapped_error = self._map_ccxt_exception(e)
                
                # Hard errors: fail immediately (no retry)
                if isinstance(mapped_error, HardError):
                    raise mapped_error
                
                # Soft errors: retry with backoff
                if attempt < self.MAX_RETRY_ATTEMPTS - 1:
                    # Calculate backoff with jitter
                    backoff = min(
                        self.BASE_BACKOFF_SEC * (2 ** attempt),
                        self.MAX_BACKOFF_SEC
                    )
                    jitter = random.uniform(0, 0.1 * backoff)
                    sleep_time = backoff + jitter
                    
                    logger.warning(f"Retry {attempt + 1}/{self.MAX_RETRY_ATTEMPTS} after {sleep_time:.2f}s: {mapped_error}")
                    time.sleep(sleep_time)
                else:
                    # Max retries exhausted
                    raise mapped_error
    
    def _get_current_timestamp_ms(self) -> int:
        """Get current timestamp in milliseconds"""
        return int(time.time() * 1000)
    
    def fetch_ticker(self, symbol: str) -> TickerSnapshot:
        """Fetch ticker snapshot"""
        def _fetch():
            ticker = self.exchange.fetch_ticker(symbol)
            return TickerSnapshot(
                exchange=self.exchange_id,
                symbol=symbol,
                bid=ticker.get('bid'),
                ask=ticker.get('ask'),
                last=ticker.get('last'),
                timestamp_ms=ticker.get('timestamp'),
                received_at_ms=self._get_current_timestamp_ms()
            )
        
        return self._retry_with_backoff(_fetch)
    
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> List[Candle]:
        """Fetch OHLCV candles"""
        def _fetch():
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            return [
                Candle(
                    exchange=self.exchange_id,
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp_ms=int(candle[0]),
                    open=float(candle[1]),
                    high=float(candle[2]),
                    low=float(candle[3]),
                    close=float(candle[4]),
                    volume=float(candle[5])
                )
                for candle in ohlcv
            ]
        
        return self._retry_with_backoff(_fetch)
    
    def fetch_order_book(self, symbol: str, depth: int = 20) -> OrderBookSnapshot:
        """Fetch orderbook snapshot"""
        def _fetch():
            orderbook = self.exchange.fetch_order_book(symbol, limit=depth)
            return OrderBookSnapshot(
                exchange=self.exchange_id,
                symbol=symbol,
                bids=[PriceLevel(price=float(b[0]), amount=float(b[1])) for b in orderbook.get('bids', [])],
                asks=[PriceLevel(price=float(a[0]), amount=float(a[1])) for a in orderbook.get('asks', [])],
                timestamp_ms=orderbook.get('timestamp'),
                received_at_ms=self._get_current_timestamp_ms()
            )
        
        return self._retry_with_backoff(_fetch)
    
    def fetch_balance(self) -> BalanceSnapshot:
        """Fetch account balance"""
        if not self._api_key or not self._secret:
            raise HardError("API credentials required for balance fetch")
        
        def _fetch():
            balance = self.exchange.fetch_balance()
            return BalanceSnapshot(
                exchange=self.exchange_id,
                total=balance.get('total', {}),
                free=balance.get('free', {}),
                used=balance.get('used', {}),
                timestamp_ms=balance.get('timestamp'),
                received_at_ms=self._get_current_timestamp_ms()
            )
        
        return self._retry_with_backoff(_fetch)
    
    def submit_order(self, order_spec: Dict[str, Any]) -> SubmitOrderResult:
        """Submit order (Epoch C dependency)"""
        if not self._api_key or not self._secret:
            raise HardError("API credentials required for order submission")
        
        def _submit():
            # Extract order params
            symbol = order_spec.get('symbol')
            side = order_spec.get('side', '').lower()
            quantity = order_spec.get('quantity')
            order_type = order_spec.get('order_type', 'market').lower()
            price = order_spec.get('price')
            client_order_id = order_spec.get('client_order_id')
            reduce_only = order_spec.get('reduce_only', False)
            
            # Build CCXT params
            params = {}
            if client_order_id:
                params['clientOrderId'] = client_order_id
            if reduce_only:
                params['reduceOnly'] = True
            
            # Submit order
            result = self.exchange.create_order(
                symbol=symbol,
                type=order_type,
                side=side,
                amount=quantity,
                price=price,
                params=params
            )
            
            # Sanitize response (remove sensitive data)
            sanitized = {k: v for k, v in result.items() if k not in ['info']}
            
            return SubmitOrderResult(
                client_order_id=client_order_id or "",
                exchange_order_id=result.get('id'),
                status=result.get('status', 'UNKNOWN').upper(),
                filled_qty=float(result.get('filled', 0)),
                avg_price=result.get('average'),
                raw_sanitized=sanitized
            )
        
        return self._retry_with_backoff(_submit)
    
    def get_order(self, client_order_id: str) -> OrderStatusResult:
        """Get order status (Epoch C dependency)"""
        if not self._api_key or not self._secret:
            raise HardError("API credentials required for order query")
        
        def _get():
            # CCXT doesn't have universal fetch_order_by_client_id
            # This is exchange-specific; implement basic version
            # Real implementation would use exchange-specific methods
            
            # For now, raise not implemented (would need exchange-specific logic)
            raise NotImplementedError(
                f"get_order by client_order_id not yet implemented for {self.exchange_id}"
            )
        
        return self._retry_with_backoff(_get)
