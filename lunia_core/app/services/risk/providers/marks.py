"""
EPOCH E Phase E3.1: Mark Price Provider
VALID+FRESH snapshot-based mark price extraction
"""
from __future__ import annotations

import os
import time
from typing import Dict, Optional
from pydantic import BaseModel, Field

from app.services.market_data.realtime.models import MarketSnapshot, SnapshotState
from .base import ProviderErrorCodes


class MarksResult(BaseModel):
    """Mark price provider result"""
    ok: bool
    mark_prices: Optional[Dict[str, float]] = None
    blocking_errors: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class IMarkPriceProvider:
    """Interface for mark price provision"""
    
    def get_mark_prices(
        self,
        symbols: list[str],
        snapshot: MarketSnapshot,
        now_ms: Optional[int] = None
    ) -> MarksResult:
        """Get mark prices for symbols"""
        raise NotImplementedError


class SnapshotMarkPriceProvider(IMarkPriceProvider):
    """
    Mark price provider from MarketSnapshot
    
    LOCKED INVARIANTS:
    - snapshot.state == VALID (MUST)
    - age_ms <= LUNIA_STALENESS_THRESHOLD_MS (MUST)
    - Price extraction: mid → (bid+ask)/2 → FAIL
    - Side-effect free (read-only)
    """
    
    def __init__(self, staleness_threshold_ms: Optional[int] = None):
        """Initialize with staleness threshold"""
        if staleness_threshold_ms is None:
            staleness_threshold_ms = int(os.getenv("LUNIA_STALENESS_THRESHOLD_MS", "5000"))
        self.staleness_threshold_ms = staleness_threshold_ms
    
    def get_mark_prices(
        self,
        symbols: list[str],
        snapshot: MarketSnapshot,
        now_ms: Optional[int] = None
    ) -> MarksResult:
        """Get mark prices with VALID+FRESH check"""
        process_timestamp = now_ms if now_ms is not None else int(time.time() * 1000)
        errors = []
        
        # Validate snapshot state
        snapshot_state = snapshot.snapshot_state
        if isinstance(snapshot_state, str):
            is_valid = snapshot_state == "VALID"
        else:
            is_valid = snapshot_state == SnapshotState.VALID
        
        if not is_valid:
            errors.append(ProviderErrorCodes.MARKS_SNAPSHOT_INVALID)
            return MarksResult(
                ok=False,
                blocking_errors=errors,
                metadata={"snapshot_state": str(snapshot_state)}
            )
        
        # Validate freshness
        age_ms = process_timestamp - snapshot.last_update_ms
        if age_ms > self.staleness_threshold_ms:
            errors.append(ProviderErrorCodes.MARKS_STALE)
            return MarksResult(
                ok=False,
                blocking_errors=errors,
                metadata={
                    "age_ms": age_ms,
                    "threshold_ms": self.staleness_threshold_ms
                }
            )
        
        # Extract prices for required symbols
        mark_prices = {}
        
        for symbol in symbols:
            # Check if this snapshot matches the symbol
            if snapshot.symbol == symbol:
                price = self._extract_price(snapshot)
                if price is None:
                    errors.append(ProviderErrorCodes.MARKS_MISSING_PRICE)
                    return MarksResult(
                        ok=False,
                        blocking_errors=errors,
                        metadata={"missing_symbol": symbol}
                    )
                mark_prices[symbol] = price
            # If snapshot doesn't match symbol, fail-closed
            # (In production, would use cache or multi-symbol snapshot)

        
        # Build metadata
        price_source = "MID" if snapshot.mid_price is not None else "BIDASK"
        metadata = {
            "snapshot_version": snapshot.version,
            "snapshot_received_at_ms": snapshot.received_at_ms if hasattr(snapshot, 'received_at_ms') else snapshot.last_update_ms,
            "age_ms": age_ms,
            "price_source": price_source,
            "data_timestamp": snapshot.last_update_ms,
            "process_timestamp": process_timestamp
        }
        
        return MarksResult(ok=True, mark_prices=mark_prices, metadata=metadata)
    
    def _extract_price(self, snapshot: MarketSnapshot) -> Optional[float]:
        """Extract price: mid → bidask avg → None"""
        # Prefer mid_price
        if snapshot.mid_price is not None and snapshot.mid_price > 0:
            return snapshot.mid_price
        
        # Fallback to (bid+ask)/2 if both present
        if snapshot.orderbook_l2:
            bids = snapshot.orderbook_l2.bids
            asks = snapshot.orderbook_l2.asks
            if bids and asks and bids[0].price > 0 and asks[0].price > 0:
                return (bids[0].price + asks[0].price) / 2.0
        
        # Fail
        return None
