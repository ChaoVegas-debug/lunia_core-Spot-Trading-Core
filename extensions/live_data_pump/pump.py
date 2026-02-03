"""
PHASE 12B — LIVE DATA PUMP: Main Pump

REST-based market data pump with external tick injection.

CRITICAL RULES:
- No wall-clock polling (external tick injection only)
- Fail-closed (never return invalid data as OK)
- Thread-safe snapshot retrieval
- Bounded memory
"""

from typing import Dict, Any, Optional
import threading

from extensions.exchange_connectivity.binance_client import BinanceClient
from .orderbook import LocalOrderBook
from .snapshot_factory import create_market_snapshot
from .store import SnapshotStore
from .models import ErrorCode


class LiveDataPump:
    """
    Live market data pump (REST-based polling).
    
    Features:
    - REST polling via Phase 12A client
    - External tick injection (no wall-clock)
    - Bounded orderbook and snapshot store
    - Thread-safe retrieval
    """
    
    def __init__(
        self,
        client: BinanceClient,
        symbol: str,
        depth: int = 20,
        max_snapshots: int = 100,
    ):
        """
        Initialize data pump.
        
        Args:
            client: BinanceClient instance
            symbol: Trading symbol (e.g., "BTCUSDT")
            depth: Orderbook depth (default 20)
            max_snapshots: Max snapshot history (default 100)
        """
        self.client = client
        self.symbol = symbol
        self.depth = depth
        
        # Components
        self.book = LocalOrderBook(symbol, depth)
        self.store = SnapshotStore(symbol, max_snapshots)
        
        # State
        self.last_ticker_price: Optional[str] = None
        self.last_ticker_ts: Optional[int] = None
        self.last_server_ts: Optional[int] = None
        self.last_event_ts: Optional[int] = None
        self.update_count = 0
        self.error_count = 0
        self.last_error: Optional[Dict[str, Any]] = None
        
        # Thread safety
        self._lock = threading.Lock()
    
    def initialize(self) -> Dict[str, Any]:
        """
        Initialize pump with REST depth snapshot.
        
        Returns:
            Result dict with ok/error
        """
        with self._lock:
            # Get depth snapshot
            depth_resp = self.client.depth(self.symbol, limit=self.depth)
            
            if not depth_resp["ok"]:
                self.last_error = depth_resp.get("error")
                self.error_count += 1
                return {
                    "ok": False,
                    "error": depth_resp.get("error"),
                }
            
            # Extract data
            depth_data = depth_resp["data"]
            bids = depth_data.get("bids", [])
            asks = depth_data.get("asks", [])
            last_update_id = depth_data.get("lastUpdateId")
            
            # Initialize book
            self.book.initialize_from_snapshot(bids, asks, last_update_id)
            
            # Get server time
            time_resp = self.client.server_time()
            if time_resp["ok"]:
                self.last_server_ts = time_resp["data"].get("serverTime")
            
            return {"ok": True, "last_update_id": last_update_id}
    
    def tick(self) -> Dict[str, Any]:
        """
        Execute one polling tick (external trigger).
        
        This method is called externally to trigger a poll.
        In production, caller controls polling frequency.
        
        Returns:
            Result dict with ok/error
        """
        with self._lock:
            results = {"depth_ok": False, "ticker_ok": False}
            
            # Poll depth
            depth_resp = self.client.depth(self.symbol, limit=self.depth)
            if depth_resp["ok"]:
                depth_data = depth_resp["data"]
                bids = depth_data.get("bids", [])
                asks = depth_data.get("asks", [])
                update_id = depth_data.get("lastUpdateId")
                
                # Apply update
                applied = self.book.apply_update(bids, asks, update_id)
                
                if not applied:
                    # Gap detected
                    self.last_error = {
                        "code": ErrorCode.DEPTH_DESYNC,
                        "message": "Gap detected in depth updates",
                        "details": {"last_update_id": self.book.last_update_id, "new_update_id": update_id}
                    }
                    self.error_count += 1
                    # Require reinitialization
                    self.book.reset()
                else:
                    results["depth_ok"] = True
            else:
                self.last_error = depth_resp.get("error")
                self.error_count += 1
            
            # Poll ticker
            ticker_resp = self.client.ticker_price(self.symbol)
            if ticker_resp["ok"]:
                ticker_data = ticker_resp["data"]
                self.last_ticker_price = ticker_data.get("price")
                results["ticker_ok"] = True
            else:
                self.last_error = ticker_resp.get("error")
                self.error_count += 1
            
            # Get server time
            time_resp = self.client.server_time()
            if time_resp["ok"]:
                self.last_server_ts = time_resp["data"].get("serverTime")
                self.last_event_ts = self.last_server_ts
            
            # Create snapshot
            if results["depth_ok"]:
                is_fresh = results["depth_ok"] and results["ticker_ok"]
                stale_reason = None if is_fresh else "PARTIAL_DATA"
                
                snapshot = create_market_snapshot(
                    self.book,
                    ticker_price=self.last_ticker_price,
                    event_ts_ms=self.last_event_ts,
                    server_ts_ms=self.last_server_ts,
                    is_fresh=is_fresh,
                    stale_reason=stale_reason,
                    last_error=self.last_error,
                )
                
                self.store.add_snapshot(snapshot)
                self.update_count += 1
            
            return {
                "ok": results["depth_ok"],
                "depth_ok": results["depth_ok"],
                "ticker_ok": results["ticker_ok"],
                "update_count": self.update_count,
                "error_count": self.error_count,
            }
    
    def get_latest_snapshot(self) -> Optional[Dict[str, Any]]:
        """
        Get latest market snapshot.
        
        Returns:
            Snapshot dict or None
        """
        return self.store.get_latest_snapshot()
    
    def get_recent_snapshots(self, limit: int = 10) -> Dict[str, Any]:
        """
        Get recent snapshots.
        
        Args:
            limit: Max snapshots to return
        
        Returns:
            Dict with snapshots list
        """
        snapshots = self.store.get_recent_snapshots(limit)
        return {
            "ok": True,
            "symbol": self.symbol,
            "snapshots": snapshots,
            "count": len(snapshots),
        }
