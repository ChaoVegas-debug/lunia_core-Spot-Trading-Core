"""
PHASE 12B — LIVE DATA PUMP: SnapshotFactory

Immutable canonical MarketSnapshot construction.
"""

from typing import Dict, Any, Optional
from .orderbook import LocalOrderBook
from .models import calculate_mid_price, calculate_spread, ErrorCode


def create_market_snapshot(
    book: LocalOrderBook,
    *,
    ticker_price: Optional[str] = None,
    ticker_qty: Optional[str] = None,
    ticker_ts_ms: Optional[int] = None,
    event_ts_ms: Optional[int] = None,
    server_ts_ms: Optional[int] = None,
    is_fresh: bool = False,
    stale_reason: Optional[str] = None,
    last_error: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create immutable market snapshot from orderbook.
    
    Args:
        book: LocalOrderBook instance
        ticker_price: Last trade price (optional)
        ticker_qty: Last trade quantity (optional)
        ticker_ts_ms: Last trade timestamp (optional)
        event_ts_ms: Event timestamp (optional)
        server_ts_ms: Server timestamp (optional)
        is_fresh: Freshness flag
        stale_reason: Reason for staleness (if not fresh)
        last_error: Last error object (if any)
    
    Returns:
        Immutable snapshot dict (canonical schema)
    """
    # Get immutable copy of book levels
    bids, asks = book.get_sorted_levels()
    best_bid, best_ask = book.get_best_bid_ask()
    
    # Calculate mid and spread
    mid = calculate_mid_price(best_bid, best_ask)
    spread = calculate_spread(best_bid, best_ask)
    
    # Build canonical snapshot
    snapshot = {
        "ok": book.is_synced,
        "symbol": book.symbol,
        "event_ts_ms": event_ts_ms,
        "server_ts_ms": server_ts_ms,
        "source": {
            "exchange": "binance",
            "mode": "rest_fallback",
            "streams": None,
        },
        "book": {
            "depth": book.depth,
            "bids": bids[:],  # Copy
            "asks": asks[:],  # Copy
            "last_update_id": book.last_update_id,
        },
        "top": {
            "best_bid": best_bid,
            "best_ask": best_ask,
            "mid": mid,
            "spread": spread,
        },
        "trade": {
            "price": ticker_price,
            "qty": ticker_qty,
            "trade_ts_ms": ticker_ts_ms,
        },
        "health": {
            "is_synced": book.is_synced,
            "is_fresh": is_fresh,
            "stale_reason": stale_reason,
            "last_error": last_error,
        },
    }
    
    return snapshot
