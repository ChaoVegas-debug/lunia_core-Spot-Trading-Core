"""
PHASE 12B — LIVE DATA PUMP: SnapshotStore

Bounded ring buffer for recent snapshots.
"""

from typing import Dict, Any, List, Optional
from collections import deque
import threading


class SnapshotStore:
    """
    Thread-safe snapshot store with bounded ring buffer.
    
    Features:
    - Bounded capacity (FIFO eviction)
    - Thread-safe access
    - Latest snapshot retrieval
    - Recent snapshot history
    """
    
    def __init__(self, symbol: str, max_snapshots: int = 100):
        """
        Initialize snapshot store.
        
        Args:
            symbol: Trading symbol
            max_snapshots: Max snapshots to retain (default 100)
        """
        self.symbol = symbol
        self.max_snapshots = max_snapshots
        
        # Ring buffer (bounded)
        self._snapshots: deque = deque(maxlen=max_snapshots)
        
        # Thread safety
        self._lock = threading.Lock()
    
    def add_snapshot(self, snapshot: Dict[str, Any]):
        """
        Add snapshot to store.
        
        Args:
            snapshot: Market snapshot dict
        """
        with self._lock:
            self._snapshots.append(snapshot)
    
    def get_latest_snapshot(self) -> Optional[Dict[str, Any]]:
        """
        Get latest snapshot.
        
        Returns:
            Latest snapshot or None if empty
        """
        with self._lock:
            if self._snapshots:
                return self._snapshots[-1].copy()  # Return copy
            return None
    
    def get_recent_snapshots(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent snapshots (oldest → newest).
        
        Args:
            limit: Max snapshots to return
        
        Returns:
            List of snapshots (copies)
        """
        with self._lock:
            # Get last N snapshots
            recent = list(self._snapshots)[-limit:]
            # Return copies
            return [s.copy() for s in recent]
    
    def clear(self):
        """Clear all snapshots."""
        with self._lock:
            self._snapshots.clear()
