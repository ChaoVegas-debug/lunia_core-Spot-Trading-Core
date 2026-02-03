"""
EPOCH D Phase D3.1: Real-Time Market Data Models
Snapshot state model with VALID/STALE/INVALID semantics
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel


class SnapshotState(str, Enum):
    """
    Snapshot health state
    
    VALID: Fresh, L2-consistent, ready for trading
    STALE: Freshness exceeded threshold OR disconnected OR partial data
    INVALID: L2 integrity violation (crossed book, bad prices, etc.)
    """
    VALID = "VALID"
    STALE = "STALE"
    INVALID = "INVALID"


class PriceLevel(BaseModel):
    """Single L2 price level"""
    price: float
    amount: float


class TickerUpdate(BaseModel):
    """Real-time ticker update from WebSocket"""
    exchange: str
    symbol: str
    market_type: str  # "spot", "swap", "future"
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    timestamp_ms: Optional[int] = None  # Exchange timestamp
    received_at_ms: int  # Local timestamp


class OrderBookL2(BaseModel):
    """Real-time L2 order book snapshot"""
    exchange: str
    symbol: str
    market_type: str
    bids: List[PriceLevel]
    asks: List[PriceLevel]
    timestamp_ms: Optional[int] = None  # Exchange timestamp
    received_at_ms: int  # Local timestamp


class MarketSnapshot(BaseModel):
    """
    Atomic market data snapshot
    
    Features:
    - Snapshot versioning (monotonic)
    - State tracking (VALID/STALE/INVALID)
    - Latency metrics
    - Partial data tracking (has_ticker, has_orderbook)
    """
    exchange: str
    symbol: str
    market_type: str
    
    # Ticker data
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    mid_price: Optional[float] = None  # (bid + ask) / 2 if both present
    
    # L2 data (top-N levels)
    bids: List[PriceLevel] = []
    asks: List[PriceLevel] = []
    
    # Timestamps
    last_update_ms: int  # Local time of last successful update
    last_exchange_ts: Optional[int] = None  # Last exchange timestamp seen
    system_latency_ms: Optional[int] = None  # received_at_ms - exchange_ts
    
    # Versioning
    version: int = 0  # Monotonic version, increments on each atomic update
    
    # Partial data tracking
    has_ticker: bool = False
    has_orderbook: bool = False
    
    # Health state
    snapshot_state: SnapshotState = SnapshotState.STALE  # Default fail-closed
    
    class Config:
        use_enum_values = True
