"""
EPOCH D: Market Data Adapter Interfaces
Strict contract for exchange adapters (CCXT and future implementations)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from ..market_data.models import (
    TickerSnapshot,
    Candle,
    OrderBookSnapshot,
    BalanceSnapshot,
    SubmitOrderResult,
    OrderStatusResult
)


class IExchangeAdapter(ABC):
    """
    Exchange Adapter Contract
    
    All exchange adapters MUST implement this interface.
    Provides market data, balance data, and order execution primitives.
    """
    
    @abstractmethod
    def fetch_ticker(self, symbol: str) -> TickerSnapshot:
        """
        Fetch current ticker snapshot for a symbol
        
        Args:
            symbol: Trading pair in unified format (e.g., "BTC/USDT")
        
        Returns:
            TickerSnapshot with bid/ask/last prices
        
        Raises:
            HardError: Invalid symbol, auth failure
            SoftError: Network/timeout/transient errors
        """
        pass
    
    @abstractmethod
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> List[Candle]:
        """
        Fetch OHLCV candles
        
        Args:
            symbol: Trading pair
            timeframe: Candle timeframe (e.g., "1m", "5m", "1h")
            limit: Number of candles (default 100, max depends on exchange)
        
        Returns:
            List of Candle objects (oldest first)
        
        Raises:
            HardError: Invalid symbol/timeframe
            SoftError: Network/timeout errors
        """
        pass
    
    @abstractmethod
    def fetch_order_book(self, symbol: str, depth: int = 20) -> OrderBookSnapshot:
        """
        Fetch order book snapshot
        
        Args:
            symbol: Trading pair
            depth: Number of price levels per side (default 20)
        
        Returns:
            OrderBookSnapshot with bids/asks
        
        Raises:
            HardError: Invalid symbol
            SoftError: Network/timeout errors
        """
        pass
    
    @abstractmethod
    def fetch_balance(self) -> BalanceSnapshot:
        """
        Fetch account balance snapshot
        
        Returns:
            BalanceSnapshot with total/free/used per asset
        
        Raises:
            HardError: Auth failure
            SoftError: Network/timeout errors
        """
        pass
    
    @abstractmethod
    def submit_order(self, order_spec: Dict[str, Any]) -> SubmitOrderResult:
        """
        Submit order to exchange (Epoch C dependency)
        
        Args:
            order_spec: Order specification dict with:
                - symbol: str
                - side: "buy" | "sell"
                - quantity: float
                - order_type: "market" | "limit"
                - price: float (optional for market orders)
                - reduce_only: bool (optional)
                - client_order_id: str (CRITICAL for idempotency)
        
        Returns:
            SubmitOrderResult with exchange_order_id, status
        
        Raises:
            HardError: Insufficient funds, invalid order, auth failure
            SoftError: Network/timeout errors (ambiguous acceptance)
        """
        pass
    
    @abstractmethod
    def get_order(self, client_order_id: str) -> OrderStatusResult:
        """
        Get order status by client_order_id (Epoch C dependency)
        
        Args:
            client_order_id: Client order ID (unique identifier)
        
        Returns:
            OrderStatusResult with status, filled_qty, avg_price
        
        Raises:
            HardError: Order not found (definitive)
            SoftError: Network/timeout errors
        """
        pass
