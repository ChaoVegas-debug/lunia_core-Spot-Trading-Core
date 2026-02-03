"""
PHASE 12B — LIVE DATA PUMP: Models

Error codes and canonical snapshot schema.
"""

from typing import Any, Dict, List, Optional
from decimal import Decimal


# ────────────────────────────────────────────────────────────────────────────────
# ERROR CODES
# ────────────────────────────────────────────────────────────────────────────────

class ErrorCode:
    """Error code enum (deterministic strings)."""
    WS_CONNECT_FAILED = "WS_CONNECT_FAILED"
    WS_DISCONNECTED = "WS_DISCONNECTED"
    WS_PARSE_ERROR = "WS_PARSE_ERROR"
    DEPTH_DESYNC = "DEPTH_DESYNC"
    RESYNC_REQUIRED = "RESYNC_REQUIRED"
    REST_FALLBACK_USED = "REST_FALLBACK_USED"
    INVALID_SYMBOL = "INVALID_SYMBOL"
    QUEUE_OVERFLOW = "QUEUE_OVERFLOW"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    NO_DATA = "NO_DATA"


# ────────────────────────────────────────────────────────────────────────────────
# HELPERS
# ────────────────────────────────────────────────────────────────────────────────

def calculate_mid_price(best_bid: Optional[str], best_ask: Optional[str]) -> Optional[str]:
    """
    Calculate mid price from bid/ask (deterministic Decimal arithmetic).
    
    Args:
        best_bid: Best bid price (string)
        best_ask: Best ask price (string)
    
    Returns:
        Mid price as string, or None if inputs missing
    """
    if not best_bid or not best_ask:
        return None
    
    try:
        bid_dec = Decimal(best_bid)
        ask_dec = Decimal(best_ask)
        mid_dec = (bid_dec + ask_dec) / Decimal("2")
        return str(mid_dec)
    except Exception:
        return None


def calculate_spread(best_bid: Optional[str], best_ask: Optional[str]) -> Optional[str]:
    """
    Calculate spread from bid/ask (deterministic Decimal arithmetic).
    
    Args:
        best_bid: Best bid price (string)
        best_ask: Best ask price (string)
    
   Returns:
        Spread as string, or None if inputs missing
    """
    if not best_bid or not best_ask:
        return None
    
    try:
        bid_dec = Decimal(best_bid)
        ask_dec = Decimal(best_ask)
        spread_dec = ask_dec - bid_dec
        return str(spread_dec)
    except Exception:
        return None
