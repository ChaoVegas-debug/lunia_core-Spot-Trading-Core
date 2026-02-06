"""
Phase 8.3: Liquidity Stress Detector
Detect liquidity stress from orderbook metrics
"""
from __future__ import annotations

import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class LiquidityStressDetector:
    """
    Detect liquidity stress from orderbook and spread metrics
    
    Provides:
    - Spread percentage
    - Orderbook imbalance (from SnapshotBuilder)
    - Depth score (bid+ask volume in top levels)
    - Liquidity stress classification (NORMAL / WARNING / CRITICAL)
    
    Stress Rules:
    - NORMAL: spread < 2x baseline, depth > threshold
    - WARNING: spread 2-5x baseline OR depth < threshold
    - CRITICAL: spread > 5x baseline OR depth collapse (<20% of baseline)
    """
    
    def __init__(
        self,
        baseline_spread_pct: float = 0.10,  # 10bps baseline spread
        baseline_depth: float = 100.0  # Baseline depth threshold
    ):
        """
        Initialize Liquidity Stress Detector
        
        Args:
            baseline_spread_pct: Baseline spread percentage (default 0.10 = 10bps)
            baseline_depth: Baseline depth threshold (default 100.0 units)
        """
        self.baseline_spread_pct = baseline_spread_pct
        self.baseline_depth = baseline_depth
        self.logger = logger
    
    def calculate_liquidity_state(
        self,
        symbol: str,
        bid: Optional[float] = None,
        ask: Optional[float] = None,
        mid_price: Optional[float] = None,
        orderbook_bids: Optional[List[Dict[str, float]]] = None,
        orderbook_asks: Optional[List[Dict[str, float]]] = None,
        imbalance: Optional[float] = None  # From SnapshotBuilder
    ) -> Dict[str, Any]:
        """
        Calculate liquidity state from orderbook data
        
        Args:
            symbol: Trading symbol
            bid: Best bid price
            ask: Best ask price
            mid_price: Mid price
            orderbook_bids: List of {"price": ..., "amount": ...} dicts
            orderbook_asks: List of {"price": ..., "amount": ...} dicts
            imbalance: Orderbook imbalance (from SnapshotBuilder)
        
        Returns:
            Liquidity state dict:
            {
                "spread_pct": float | None,
                "imbalance": float | None,
                "depth_score": float | None,
                "liquidity_stress": "NORMAL" | "WARNING" | "CRITICAL" | None
            }
        """
        try:
            # Calculate spread percentage
            spread_pct = self._calculate_spread_pct(bid, ask, mid_price)
            
            # Calculate depth score
            depth_score = self._calculate_depth_score(orderbook_bids, orderbook_asks)
            
            # Classify liquidity stress
            liquidity_stress = self._classify_stress(spread_pct, depth_score)
            
            return {
                "spread_pct": spread_pct,
                "imbalance": imbalance,  # Pass-through from SnapshotBuilder
                "depth_score": depth_score,
                "liquidity_stress": liquidity_stress
            }
        
        except Exception as e:
            self.logger.error(f"Liquidity calculation error for {symbol}: {e}", exc_info=True)
            return {
                "spread_pct": None,
                "imbalance": imbalance,
                "depth_score": None,
                "liquidity_stress": None
            }
    
    def _calculate_spread_pct(
        self,
        bid: Optional[float],
        ask: Optional[float],
        mid_price: Optional[float]
    ) -> Optional[float]:
        """
        Calculate spread as percentage of mid price
        
        Args:
            bid: Best bid
            ask: Best ask
            mid_price: Mid price
        
        Returns:
            Spread percentage or None
        """
        if bid is None or ask is None or mid_price is None or mid_price == 0:
            return None
        
        spread_abs = ask - bid
        spread_pct = (spread_abs / mid_price) * 100  # Convert to percentage
        
        return spread_pct
    
    def _calculate_depth_score(
        self,
        orderbook_bids: Optional[List[Dict[str, float]]],
        orderbook_asks: Optional[List[Dict[str, float]]],
        top_n: int = 5
    ) -> Optional[float]:
        """
        Calculate depth score (total volume in top N levels)
        
        Args:
            orderbook_bids: List of bid levels
            orderbook_asks: List of ask levels
            top_n: Number of top levels to include (default 5)
        
        Returns:
            Depth score (sum of bid+ask volumes) or None
        """
        if not orderbook_bids or not orderbook_asks:
            return None
        
        # Sum top N bid volumes
        bid_depth = sum(
            level.get("amount", 0)
            for level in orderbook_bids[:top_n]
        )
        
        # Sum top N ask volumes
        ask_depth = sum(
            level.get("amount", 0)
            for level in orderbook_asks[:top_n]
        )
        
        depth_score = bid_depth + ask_depth
        return depth_score
    
    def _classify_stress(
        self,
        spread_pct: Optional[float],
        depth_score: Optional[float]
    ) -> Optional[str]:
        """
        Classify liquidity stress level
        
        Rules:
        - NORMAL: spread < 2x baseline AND depth > baseline
        - WARNING: spread 2-5x baseline OR depth < baseline
        - CRITICAL: spread > 5x baseline OR depth < 20% baseline
        
        Args:
            spread_pct: Spread percentage
            depth_score: Depth score
        
        Returns:
            "NORMAL" | "WARNING" | "CRITICAL" | None
        """
        # Need at least one metric
        if spread_pct is None and depth_score is None:
            return None
        
        # Check for CRITICAL conditions
        if spread_pct is not None:
            if spread_pct > 5 * self.baseline_spread_pct:
                return "CRITICAL"
        
        if depth_score is not None:
            if depth_score < 0.2 * self.baseline_depth:
                return "CRITICAL"
        
        # Check for WARNING conditions
        if spread_pct is not None:
            if spread_pct > 2 * self.baseline_spread_pct:
                return "WARNING"
        
        if depth_score is not None:
            if depth_score < self.baseline_depth:
                return "WARNING"
        
        # Otherwise NORMAL
        return "NORMAL"
