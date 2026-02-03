"""
EPOCH D: Normalized Market Data Models
Strict Pydantic v1 models - NO raw CCXT dictionaries
"""
from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class TickerSnapshot(BaseModel):
    """
    Normalized ticker snapshot
    """
    exchange: str
    symbol: str
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    timestamp_ms: Optional[int] = None  # Exchange timestamp
    received_at_ms: int  # Local timestamp (forensic)


class Candle(BaseModel):
    """
    Normalized OHLCV candle
    """
    exchange: str
    symbol: str
    timeframe: str
    timestamp_ms: int  # Candle open time
    open: float
    high: float
    low: float
    close: float
    volume: float


class PriceLevel(BaseModel):
    """
    Single order book price level
    """
    price: float
    amount: float


class OrderBookSnapshot(BaseModel):
    """
    Normalized order book snapshot
    """
    exchange: str
    symbol: str
    bids: List[PriceLevel]
    asks: List[PriceLevel]
    timestamp_ms: Optional[int] = None  # Exchange timestamp
    received_at_ms: int  # Local timestamp


class BalanceSnapshot(BaseModel):
    """
    Normalized account balance snapshot
    """
    exchange: str
    total: Dict[str, float]  # Total balance per asset
    free: Dict[str, float]   # Available balance
    used: Dict[str, float]   # Locked in orders
    timestamp_ms: Optional[int] = None
    received_at_ms: int


class SubmitOrderResult(BaseModel):
    """
    Order submission result (Epoch C compatibility)
    """
    client_order_id: str
    exchange_order_id: Optional[str] = None
    status: str  # "NEW", "FILLED", "REJECTED", etc.
    filled_qty: float = 0.0
    avg_price: Optional[float] = None
    raw_sanitized: Dict = Field(default_factory=dict)  # Sanitized exchange response


class OrderStatusResult(BaseModel):
    """
    Order status query result (Epoch C compatibility)
    """
    client_order_id: str
    exchange_order_id: Optional[str] = None
    status: str  # "NEW", "FILLED", "PARTIALLY_FILLED", "CANCELLED", etc.
    filled_qty: float = 0.0
    avg_price: Optional[float] = None
    raw_sanitized: Dict = Field(default_factory=dict)
