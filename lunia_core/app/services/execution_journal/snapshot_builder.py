"""
Phase 8.2A: Context Snapshot Builder
Builds L1/L2/L3 snapshots with memory bounds and truncation
"""
from __future__ import annotations

import json
import logging
from typing import Dict, Any, Optional, List

from ..market_data.realtime.models import MarketSnapshot, PriceLevel

logger = logging.getLogger(__name__)

# Memory bound: max 10KB serialized JSON
MAX_SNAPSHOT_BYTES = 10 * 1024  # 10KB


class SnapshotBuilder:
    """
    Multi-level context snapshot builder
    
    Levels:
    - L1 (MANDATORY): Price, spread, volume proxy, volatility proxy
    - L2 (MICROSTRUCTURE): Top-N orderbook, imbalance, liquidity gaps
    - L3 (SYSTEMIC): Portfolio, PnL, DEFCON, uptime (best-effort)
    
    HARD LAWS:
    - L1 NEVER truncated
    - L2 orderbook depth reduced before truncation
    - L3 dropped first if size exceeded
    - Max serialized size: 10,240 bytes
    """
    
    def __init__(self, max_orderbook_levels: int = 10):
        """
        Initialize snapshot builder
        
        Args:
            max_orderbook_levels: Max orderbook depth for L2 (default 10)
        """
        self.max_orderbook_levels = max_orderbook_levels
    
    def build_l1(self, snapshot: MarketSnapshot) -> Dict[str, Any]:
        """
        Build LEVEL 1 snapshot (mandatory, sync capture)
        
        Args:
            snapshot: MarketSnapshot from StrategyContext
        
        Returns:
            L1 snapshot dict
        """
        # Price data
        mid = snapshot.mid_price
        bid = snapshot.bid
        ask = snapshot.ask
        last = snapshot.last
        
        # Spread calculation
        spread_abs = None
        spread_rel = None
        if bid is not None and ask is not None:
            spread_abs = ask - bid
            if mid and mid > 0:
                spread_rel = spread_abs / mid
        
        # Volume proxy (NOT available in MarketSnapshot for v1)
        volume_current = None
        volume_1m_avg = None
        
        # Volatility proxy (spread-based for v1; ATR not available)
        volatility_proxy = spread_rel  # Use spread as volatility indicator
        
        # Regime flags (NOT available for v1)
        regime_flags = None
        
        # Risk filters (NOT available at snapshot build time)
        risk_filters_triggered = None
        
        return {
            "level": "L1",
            "price": {
                "mid": mid,
                "bid": bid,
                "ask": ask,
                "last": last
            },
            "spread": {
                "abs": spread_abs,
                "rel": spread_rel
            },
            "volume": {
                "current": volume_current,
                "1m_avg": volume_1m_avg
            },
            "volatility_proxy": volatility_proxy,
            "regime_flags": regime_flags,
            "risk_filters_triggered": risk_filters_triggered,
            "snapshot_state": snapshot.snapshot_state.value if hasattr(snapshot.snapshot_state, 'value') else str(snapshot.snapshot_state)
        }
    
    def build_l2(self, snapshot: MarketSnapshot, max_levels: Optional[int] = None) -> Dict[str, Any]:
        """
        Build LEVEL 2 snapshot (microstructure, sync capture)
        
        Args:
            snapshot: MarketSnapshot from StrategyContext
            max_levels: Override max orderbook levels (for truncation)
        
        Returns:
            L2 snapshot dict
        """
        n = max_levels if max_levels is not None else self.max_orderbook_levels
        
        # Orderbook top-N
        orderbook_bids = [
            {"price": level.price, "amount": level.amount}
            for level in snapshot.bids[:n]
        ]
        orderbook_asks = [
            {"price": level.price, "amount": level.amount}
            for level in snapshot.asks[:n]
        ]
        
        # Imbalance calculation
        bid_vol = sum(level.amount for level in snapshot.bids[:n])
        ask_vol = sum(level.amount for level in snapshot.asks[:n])
        
        imbalance = None
        if (bid_vol + ask_vol) > 0:
            imbalance = (bid_vol - ask_vol) / (bid_vol + ask_vol)
        
        # Liquidity gaps (within top 20 levels if available)
        liquidity_gaps = self._calculate_liquidity_gaps(snapshot.bids[:20], snapshot.asks[:20])
        
        # Micro volatility (NOT available; no tick buffer)
        micro_volatility = None
        
        return {
            "level": "L2",
            "orderbook_top_n": {
                "n": n,
                "bids": orderbook_bids,
                "asks": orderbook_asks
            },
            "imbalance": imbalance,
            "liquidity_gaps": liquidity_gaps,
            "micro_volatility": micro_volatility
        }
    
    def build_l3(self) -> Dict[str, Any]:
        """
        Build LEVEL 3 snapshot (systemic, best-effort)
        
        Returns:
            L3 snapshot dict (mostly None for v1)
        """
        # All L3 fields unavailable in v1 system
        return {
            "level": "L3",
            "portfolio_exposure": None,
            "system_pnl": None,
            "defcon_level": None,
            "system_uptime_seconds": None,
            "correlation_matrix_signature": None
        }
    
    def build_full_snapshot(
        self,
        snapshot: MarketSnapshot,
        include_l2: bool = True,
        include_l3: bool = True
    ) -> Dict[str, Any]:
        """
        Build full multi-level snapshot with memory bounds
        
        Args:
            snapshot: MarketSnapshot from StrategyContext
            include_l2: Include L2 microstructure (default True)
            include_l3: Include L3 systemic (default True)
        
        Returns:
            Full snapshot dict with truncation applied if needed
        """
        full_snapshot = {
            "snapshot_meta": {
                "timestamp_ms": snapshot.last_update_ms,
                "snapshot_version": snapshot.version,
                "truncated": False,
                "truncation_reason": None
            },
            "l1": self.build_l1(snapshot)
        }
        
        if include_l2:
            full_snapshot["l2"] = self.build_l2(snapshot)
        
        if include_l3:
            full_snapshot["l3"] = self.build_l3()
        
        # Enforce memory bound
        full_snapshot = self._enforce_memory_bound(full_snapshot, snapshot)
        
        return full_snapshot
    
    def _enforce_memory_bound(
        self,
        snapshot: Dict[str, Any],
        market_snapshot: MarketSnapshot
    ) -> Dict[str, Any]:
        """
        Enforce 10KB memory bound with truncation
        
        Truncation priority:
        1. Drop L3 fields
        2. Reduce L2 orderbook depth (10 → 5 → 2)
        3. NEVER drop L1
        
        Args:
            snapshot: Full snapshot dict
            market_snapshot: Original MarketSnapshot (for re-building L2)
        
        Returns:
            Truncated snapshot if needed
        """
        serialized = json.dumps(snapshot)
        size_bytes = len(serialized.encode('utf-8'))
        
        if size_bytes <= MAX_SNAPSHOT_BYTES:
            return snapshot
        
        logger.warning(f"Snapshot size {size_bytes} bytes exceeds limit {MAX_SNAPSHOT_BYTES}, truncating...")
        
        # Priority 1: Drop L3
        if "l3" in snapshot:
            snapshot.pop("l3")
            snapshot["snapshot_meta"]["truncated"] = True
            snapshot["snapshot_meta"]["truncation_reason"] = "l3_dropped"
            
            serialized = json.dumps(snapshot)
            size_bytes = len(serialized.encode('utf-8'))
            
            if size_bytes <= MAX_SNAPSHOT_BYTES:
                logger.info(f"Truncated snapshot (L3 dropped): {size_bytes} bytes")
                return snapshot
        
        # Priority 2: Reduce L2 orderbook depth
        if "l2" in snapshot:
            for depth in [5, 2]:
                snapshot["l2"] = self.build_l2(market_snapshot, max_levels=depth)
                snapshot["snapshot_meta"]["truncation_reason"] = f"l2_orderbook_reduced_to_{depth}"
                
                serialized = json.dumps(snapshot)
                size_bytes = len(serialized.encode('utf-8'))
                
                if size_bytes <= MAX_SNAPSHOT_BYTES:
                    logger.info(f"Truncated snapshot (L2 depth={depth}): {size_bytes} bytes")
                    return snapshot
            
            # Still too large: drop L2 entirely
            snapshot.pop("l2")
            snapshot["snapshot_meta"]["truncation_reason"] = "l2_dropped"
            
            serialized = json.dumps(snapshot)
            size_bytes = len(serialized.encode('utf-8'))
            
            logger.warning(f"Truncated snapshot (L2 dropped): {size_bytes} bytes")
        
        # L1 NEVER dropped (even if still over limit)
        return snapshot
    
    def _calculate_liquidity_gaps(
        self,
        bids: List[PriceLevel],
        asks: List[PriceLevel]
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate liquidity gaps in orderbook
        
        Args:
            bids: Bid levels
            asks: Ask levels
        
        Returns:
            Liquidity gap metrics or None
        """
        if not bids or not asks:
            return None
        
        # Simple gap detection: largest price gap between consecutive levels
        bid_gaps = []
        for i in range(len(bids) - 1):
            gap = abs(bids[i].price - bids[i+1].price)
            bid_gaps.append(gap)
        
        ask_gaps = []
        for i in range(len(asks) - 1):
            gap = abs(asks[i].price - asks[i+1].price)
            ask_gaps.append(gap)
        
        return {
            "max_bid_gap": max(bid_gaps) if bid_gaps else None,
            "max_ask_gap": max(ask_gaps) if ask_gaps else None,
            "avg_bid_gap": sum(bid_gaps) / len(bid_gaps) if bid_gaps else None,
            "avg_ask_gap": sum(ask_gaps) / len(ask_gaps) if ask_gaps else None
        }
