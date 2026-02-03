"""
PHASE 14B — LIVE ADAPTER: Trade Models

Normalized execution outcomes for write operations.

CRITICAL RULES:
- Adapter has HANDS, not BRAIN
- No decision logic (only execution + normalization)
- UNKNOWN for network ambiguity (fail-safe)
- Decimal-only for all numeric fields
- Deterministic serialization
"""

import hashlib
from decimal import Decimal
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, Literal


# ────────────────────────────────────────────────────────────────────────────────
# TYPE ALIASES
# ────────────────────────────────────────────────────────────────────────────────

OrderStatus = Literal[
    "NEW",              # Order accepted, not filled
    "PARTIALLY_FILLED", # Order partially filled
    "FILLED",           # Order completely filled
    "CANCELED",         # Order canceled
    "REJECTED",         # Exchange rejected (definitive)
    "UNKNOWN",          # Network ambiguity (timeout, connection error)
]

OrderSide = Literal["BUY", "SELL"]
OrderType = Literal["MARKET", "LIMIT"]


# ────────────────────────────────────────────────────────────────────────────────
# ORDER RESULT (Normalized Output)
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class OrderResult:
    """
    Normalized order execution result.
    
    The adapter returns ONLY this type (never raw JSON).
    
    Fields:
    - order_id: Exchange order ID (None if rejected/unknown)
    - client_order_id: Client-generated order ID
    - symbol: Trading pair (e.g., "BTCUSDT")
    - status: Order status enum
    - filled_qty: Quantity filled (Decimal)
    - avg_price: Average fill price (Decimal, 0 if not filled)
    - fees: Trading fees (Decimal, 0 if unknown)
    - raw: Optional raw exchange response (debug only)
    
    Invariants:
    - UNKNOWN: network ambiguity (timeout, connection error)
    - REJECTED: definitive exchange rejection only
    - All numeric fields are Decimal (never float)
    - status must be one of 6 enum values
    """
    order_id: Optional[str]
    client_order_id: Optional[str]
    symbol: str
    status: OrderStatus
    filled_qty: Decimal
    avg_price: Decimal
    fees: Decimal
    raw: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict (Decimal → str)."""
        return {
            "order_id": self.order_id,
            "client_order_id": self.client_order_id,
            "symbol": self.symbol,
            "status": self.status,
            "filled_qty": str(self.filled_qty),
            "avg_price": str(self.avg_price),
            "fees": str(self.fees),
            "raw": self.raw,
        }


# ────────────────────────────────────────────────────────────────────────────────
# HELPERS
# ────────────────────────────────────────────────────────────────────────────────

def generate_client_order_id(symbol: str, timestamp_ms: int, nonce: str = "") -> str:
    """
    Generate deterministic client_order_id.
    
    Format: {symbol}_{timestamp_ms}_{hash}
    
    Args:
        symbol: Trading symbol
        timestamp_ms: Server timestamp (from exchange)
        nonce: Optional nonce for uniqueness
    
    Returns:
        Deterministic client_order_id (unique, reproducible)
    
    Example:
        >>> generate_client_order_id("BTCUSDT", 1704067200000, "test")
        'BTCUSDT_1704067200000_a1b2c3d4'
    """
    payload = f"{symbol}_{timestamp_ms}_{nonce}"
    hash_suffix = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8]
    return f"{symbol}_{timestamp_ms}_{hash_suffix}"


def safe_decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    """
    Safe Decimal parsing (fail-safe).
    
    Args:
        value: Value to parse (str, int, float, Decimal)
        default: Default value if parsing fails
    
    Returns:
        Decimal or default
    """
    if value is None:
        return default
    
    if isinstance(value, Decimal):
        return value
    
    try:
        return Decimal(str(value))
    except Exception:
        return default


def parse_binance_order_response(
    response: Dict[str, Any],
    symbol: str,
    client_order_id: Optional[str] = None,
) -> OrderResult:
    """
    Parse Binance order response → OrderResult.
    
    Binance order response schema:
    {
        "orderId": 123456,
        "clientOrderId": "myOrder1",
        "symbol": "BTCUSDT",
        "status": "FILLED",  # NEW, PARTIALLY_FILLED, FILLED, CANCELED, REJECTED
        "executedQty": "0.001",
        "cummulativeQuoteQty": "50.0",
        "fills": [
            {"price": "50000", "qty": "0.001", "commission": "0.00001", "commissionAsset": "BTC"}
        ]
    }
    
    Args:
        response: Raw Binance response dict
        symbol: Expected symbol
        client_order_id: Expected client_order_id (optional)
    
    Returns:
        OrderResult (normalized)
    """
    # Extract fields
    order_id = str(response.get("orderId", "")) if response.get("orderId") else None
    parsed_client_order_id = response.get("clientOrderId") or client_order_id
    
    # Status mapping
    raw_status = response.get("status", "UNKNOWN")
    status_map = {
        "NEW": "NEW",
        "PARTIALLY_FILLED": "PARTIALLY_FILLED",
        "FILLED": "FILLED",
        "CANCELED": "CANCELED",
        "REJECTED": "REJECTED",
        "EXPIRED": "CANCELED",  # Map EXPIRED → CANCELED
        "PENDING_CANCEL": "CANCELED",
    }
    status: OrderStatus = status_map.get(raw_status, "UNKNOWN")  # type: ignore
    
    # Filled quantity
    filled_qty = safe_decimal(response.get("executedQty"), Decimal("0"))
    
    # Average price calculation
    cumulative_quote_qty = safe_decimal(response.get("cummulativeQuoteQty"), Decimal("0"))
    if filled_qty > 0 and cumulative_quote_qty > 0:
        avg_price = cumulative_quote_qty / filled_qty
    else:
        avg_price = Decimal("0")
    
    # Fees calculation (sum all fills)
    fills = response.get("fills", [])
    total_fees = Decimal("0")
    for fill in fills:
        commission = safe_decimal(fill.get("commission"), Decimal("0"))
        total_fees += commission
    
    return OrderResult(
        order_id=order_id,
        client_order_id=parsed_client_order_id,
        symbol=symbol,
        status=status,
        filled_qty=filled_qty,
        avg_price=avg_price,
        fees=total_fees,
        raw=response,
    )


def parse_binance_error_to_order_result(
    error_code: str,
    error_message: str,
    symbol: str,
    client_order_id: Optional[str] = None,
) -> OrderResult:
    """
    Convert error → OrderResult with appropriate status.
    
    Rules:
    - Definitive exchange rejection → REJECTED
    - Network/timeout ambiguity → UNKNOWN
    
    Args:
        error_code: Error code from exchange or internal
        error_message: Error message
        symbol: Trading symbol
        client_order_id: Client order ID (optional)
    
    Returns:
        OrderResult with REJECTED or UNKNOWN status
    """
    # Binance error codes that are REJECTED (definitive)
    rejected_codes = [
        "INVALID_ORDER",
        "INSUFFICIENT_BALANCE",
        "MIN_NOTIONAL",
        "MARKET_CLOSED",
        "INVALID_PRICE",
        "INVALID_QUANTITY",
        "DUPLICATE_ORDER",
    ]
    
    # Check if definitive rejection
    is_rejected = any(code in error_code.upper() for code in rejected_codes)
    
    status: OrderStatus = "REJECTED" if is_rejected else "UNKNOWN"
    
    return OrderResult(
        order_id=None,
        client_order_id=client_order_id,
        symbol=symbol,
        status=status,
        filled_qty=Decimal("0"),
        avg_price=Decimal("0"),
        fees=Decimal("0"),
        raw={"error_code": error_code, "error_message": error_message},
    )
