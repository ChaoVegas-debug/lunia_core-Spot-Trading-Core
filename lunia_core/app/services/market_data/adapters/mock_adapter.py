"""
EPOCH D: Mock Exchange Adapter
For unit testing and future D2/D3 development
"""
from __future__ import annotations

from typing import Any, Dict, List
import time

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


class MockExchangeAdapter(IExchangeAdapter):
    """
    Mock exchange adapter for testing
    
    Returns deterministic static data.
    Can be configured to raise specific errors for testing error mapping.
    """
    
    def __init__(self, exchange_id: str = "mock_exchange"):
        self.exchange_id = exchange_id
        self._should_raise: Dict[str, Exception] = {}
    
    def configure_error(self, method_name: str, error: Exception):
        """Configure method to raise specific error"""
        self._should_raise[method_name] = error
    
    def _check_error(self, method_name: str):
        """Check if method should raise error"""
        if method_name in self._should_raise:
            raise self._should_raise[method_name]
    
    def fetch_ticker(self, symbol: str) -> TickerSnapshot:
        """Return mock ticker"""
        self._check_error("fetch_ticker")
        
        return TickerSnapshot(
            exchange=self.exchange_id,
            symbol=symbol,
            bid=50000.0,
            ask=50001.0,
            last=50000.5,
            timestamp_ms=int(time.time() * 1000),
            received_at_ms=int(time.time() * 1000)
        )
    
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> List[Candle]:
        """Return mock candles"""
        self._check_error("fetch_ohlcv")
        
        base_ts = int(time.time() * 1000) - (limit * 60000)  # 1min candles
        
        return [
            Candle(
                exchange=self.exchange_id,
                symbol=symbol,
                timeframe=timeframe,
                timestamp_ms=base_ts + (i * 60000),
                open=50000.0 + i,
                high=50100.0 + i,
                low=49900.0 + i,
                close=50000.0 + i,
                volume=100.0
            )
            for i in range(min(limit, 10))  # Return max 10 for brevity
        ]
    
    def fetch_order_book(self, symbol: str, depth: int = 20) -> OrderBookSnapshot:
        """Return mock orderbook"""
        self._check_error("fetch_order_book")
        
        return OrderBookSnapshot(
            exchange=self.exchange_id,
            symbol=symbol,
            bids=[PriceLevel(price=50000.0 - i, amount=1.0) for i in range(depth)],
            asks=[PriceLevel(price=50001.0 + i, amount=1.0) for i in range(depth)],
            timestamp_ms=int(time.time() * 1000),
            received_at_ms=int(time.time() * 1000)
        )
    
    def fetch_balance(self) -> BalanceSnapshot:
        """Return mock balance"""
        self._check_error("fetch_balance")
        
        return BalanceSnapshot(
            exchange=self.exchange_id,
            total={"BTC": 1.0, "USDT": 50000.0},
            free={"BTC": 0.9, "USDT": 45000.0},
            used={"BTC": 0.1, "USDT": 5000.0},
            timestamp_ms=int(time.time() * 1000),
            received_at_ms=int(time.time() * 1000)
        )
    
    def submit_order(self, order_spec: Dict[str, Any]) -> SubmitOrderResult:
        """Return mock submit result"""
        self._check_error("submit_order")
        
        return SubmitOrderResult(
            client_order_id=order_spec.get("client_order_id", ""),
            exchange_order_id="MOCK_ORDER_12345",
            status="NEW",
            filled_qty=0.0,
            avg_price=None,
            raw_sanitized={"orderId": "MOCK_ORDER_12345"}
        )
    
    def get_order(self, client_order_id: str) -> OrderStatusResult:
        """Return mock order status"""
        self._check_error("get_order")
        
        return OrderStatusResult(
            client_order_id=client_order_id,
            exchange_order_id="MOCK_ORDER_12345",
            status="FILLED",
            filled_qty=0.1,
            avg_price=50000.0,
            raw_sanitized={"orderId": "MOCK_ORDER_12345", "status": "FILLED"}
        )
