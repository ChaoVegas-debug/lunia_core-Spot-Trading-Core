"""
PHASE 12B — LIVE DATA PUMP: LocalOrderBook

Bounded orderbook with canonical sorting and gap detection.

CRITICAL RULES:
- Top N levels only (bounded)
- Canonical sorting: bids DESC, asks ASC
- Prices/quantities as strings (no float conversion)
- Gap detection for lastUpdateId tracking
- Thread-safe under async event loop
"""

from typing import Dict, List, Optional, Tuple
from collections import OrderedDict
import threading


class LocalOrderBook:
    """
    Local order book with bounded depth and gap detection.
    
    Features:
    - Top N levels (configurable, default 20)
    - Canonical sorting (bids DESC, asks ASC)
    - Gap detection via lastUpdateId
    - Immutable snapshots
    """
    
    def __init__(self, symbol: str, depth: int = 20):
        """
        Initialize order book.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            depth: Max levels to maintain (default 20)
        """
        self.symbol = symbol
        self.depth = depth
        
        # Orderbook levels: price (str) -> qty (str)
        self._bids: Dict[str, str] = {}
        self._asks: Dict[str, str] = {}
        
        # Gap detection
        self.last_update_id: Optional[int] = None
        self.is_synced = False
        
        # Thread safety
        self._lock = threading.Lock()
    
    def initialize_from_snapshot(self, bids: List[List[str]], asks: List[List[str]], last_update_id: int):
        """
        Initialize book from REST snapshot.
        
        Args:
            bids: List of [price, qty] pairs
            asks: List of [price, qty] pairs
            last_update_id: Snapshot's lastUpdateId
        """
        with self._lock:
            self._bids.clear()
            self._asks.clear()
            
            # Apply bids
            for price, qty in bids:
                if qty != "0" and qty != "0.00000000":
                    self._bids[price] = qty
            
            # Apply asks
            for price, qty in asks:
                if qty != "0" and qty != "0.00000000":
                    self._asks[price] = qty
            
            self.last_update_id = last_update_id
            self.is_synced = True
    
    def apply_update(self, bids: List[List[str]], asks: List[List[str]], update_id: Optional[int] = None) -> bool:
        """
        Apply incremental update.
        
        Args:
            bids: Updated bid levels [[price, qty], ...]
            asks: Updated ask levels [[price, qty], ...]
            update_id: Update ID (for gap detection)
        
        Returns:
            True if applied successfully, False if gap detected
        """
        with self._lock:
            # Gap detection (if tracking update IDs)
            if update_id is not None and self.last_update_id is not None:
                # Simple rule: update_id should be > last_update_id
                # (Binance specific rules may vary; simplified here)
                if update_id <= self.last_update_id:
                    # Stale update, skip
                    return True
                
                # Check for gap (missing updates)
                # For simplicity: if gap > 1, require resync
                gap = update_id - self.last_update_id
                if gap > 1:
                    self.is_synced = False
                    return False
            
            # Apply bids
            for price, qty in bids:
                if qty == "0" or qty == "0.00000000":
                    self._bids.pop(price, None)
                else:
                    self._bids[price] = qty
            
            # Apply asks
            for price, qty in asks:
                if qty == "0" or qty == "0.00000000":
                    self._asks.pop(price, None)
                else:
                    self._asks[price] = qty
            
            if update_id is not None:
                self.last_update_id = update_id
            
            return True
    
    def get_sorted_levels(self) -> Tuple[List[List[str]], List[List[str]]]:
        """
        Get canonical sorted levels (top N).
        
        Returns:
            (bids, asks) where bids sorted DESC, asks sorted ASC
        """
        with self._lock:
            # Sort bids descending (highest price first)
            sorted_bids = sorted(
                self._bids.items(),
                key=lambda x: float(x[0]),  # Sort by price numerically
                reverse=True
            )
            
            # Sort asks ascending (lowest price first)
            sorted_asks = sorted(
                self._asks.items(),
                key=lambda x: float(x[0]),
                reverse=False
            )
            
            # Trim to depth
            bids_trimmed = [[price, qty] for price, qty in sorted_bids[:self.depth]]
            asks_trimmed = [[price, qty] for price, qty in sorted_asks[:self.depth]]
            
            return bids_trimmed, asks_trimmed
    
    def get_best_bid_ask(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Get best bid and ask prices.
        
        Returns:
            (best_bid, best_ask) or (None, None)
        """
        with self._lock:
            best_bid = None
            best_ask = None
            
            if self._bids:
                best_bid = max(self._bids.keys(), key=lambda x: float(x))
            
            if self._asks:
                best_ask = min(self._asks.keys(), key=lambda x: float(x))
            
            return best_bid, best_ask
    
    def reset(self):
        """Reset book to unsynced state."""
        with self._lock:
            self._bids.clear()
            self._asks.clear()
            self.last_update_id = None
            self.is_synced = False
