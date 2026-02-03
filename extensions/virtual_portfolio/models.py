"""
PHASE 13B — VIRTUAL PORTFOLIO: Models

Deterministic data contracts for portfolio accounting.

CRITICAL RULES:
- All prices/quantities/pnl use Decimal (no floats)
- All dataclasses are JSON-serializable via to_dict()
- Fail-closed error schema: {code, message, details}
"""

from dataclasses import dataclass, asdict, field
from decimal import Decimal
from typing import Dict, Any, Optional, Literal, List


# ────────────────────────────────────────────────────────────────────────────────
# TYPE ALIASES
# ────────────────────────────────────────────────────────────────────────────────

PositionSide = Literal["LONG", "SHORT", "FLAT"]
RiskLevel = Literal["OK", "WARNING", "CRITICAL"]


# ────────────────────────────────────────────────────────────────────────────────
# VIRTUAL POSITION
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class VirtualPosition:
    """
    Virtual position for a single symbol (WAP accounting).
    
    Invariants:
    - FLAT => qty == 0 AND avg_entry_price is None
    - LONG/SHORT => qty > 0 AND avg_entry_price is not None
    - mark_price may be None => unrealized_pnl MUST be 0 (fail-closed)
    """
    symbol: str
    side: PositionSide
    qty: Decimal
    avg_entry_price: Optional[Decimal]
    mark_price: Optional[Decimal]
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    last_ts_ms: Optional[int]
    trade_count: int
    last_error: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict (Decimal → str)."""
        return {
            "symbol": self.symbol,
            "side": self.side,
            "qty": str(self.qty),
            "avg_entry_price": str(self.avg_entry_price) if self.avg_entry_price is not None else None,
            "mark_price": str(self.mark_price) if self.mark_price is not None else None,
            "unrealized_pnl": str(self.unrealized_pnl),
            "realized_pnl": str(self.realized_pnl),
            "last_ts_ms": self.last_ts_ms,
            "trade_count": self.trade_count,
            "last_error": self.last_error,
        }


# ────────────────────────────────────────────────────────────────────────────────
# RISK ALERT
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class RiskAlert:
    """Risk alert event."""
    ts_ms: Optional[int]
    level: RiskLevel
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return asdict(self)


# ────────────────────────────────────────────────────────────────────────────────
# PORTFOLIO STATE
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class PortfolioState:
    """
    Global portfolio state (aggregated across all positions).
    
    ts_ms: Deterministic aggregator timestamp (max of per-symbol last_ts_ms ignoring None)
    """
    ts_ms: Optional[int]
    equity: Decimal
    starting_equity: Decimal
    realized_pnl_total: Decimal
    unrealized_pnl_total: Decimal
    drawdown_abs: Decimal
    drawdown_pct: Decimal
    positions: Dict[str, VirtualPosition]
    alerts: List[RiskAlert]
    last_error: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict (Decimal → str)."""
        return {
            "ts_ms": self.ts_ms,
            "equity": str(self.equity),
            "starting_equity": str(self.starting_equity),
            "realized_pnl_total": str(self.realized_pnl_total),
            "unrealized_pnl_total": str(self.unrealized_pnl_total),
            "drawdown_abs": str(self.drawdown_abs),
            "drawdown_pct": str(self.drawdown_pct),
            "positions": {symbol: pos.to_dict() for symbol, pos in self.positions.items()},
            "alerts": [alert.to_dict() for alert in self.alerts],
            "last_error": self.last_error,
        }


# ────────────────────────────────────────────────────────────────────────────────
# ERROR CODES
# ────────────────────────────────────────────────────────────────────────────────

class PortfolioErrorCode:
    """Error code constants."""
    INVALID_PRICE = "INVALID_PRICE"
    INVALID_QUANTITY = "INVALID_QUANTITY"
    INVALID_SIDE = "INVALID_SIDE"
    DECIMAL_PARSE_ERROR = "DECIMAL_PARSE_ERROR"
    POSITION_NOT_FOUND = "POSITION_NOT_FOUND"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
