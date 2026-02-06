"""
Phase 8.3: Volume Engine
Rolling volume analysis and trend detection
"""
from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


class VolumeEngine:
    """
    Calculate rolling volume metrics and detect volume trends
    
    Provides:
    - Rolling volume (1m / 5m / 15m)
    - Relative volume (current vs rolling average)
    - Volume trend detection (INCREASING / DECREASING / FLAT)
    
    Gracefully degrades if data unavailable (all fields → None)
    """
    
    def __init__(self):
        """Initialize Volume Engine"""
        self.logger = logger
    
    def calculate_volume_state(
        self,
        symbol: str,
        current_volume: Optional[float] = None,
        historical_volumes: Optional[List[Tuple[int, float]]] = None,
        lookback_periods: Optional[Dict[str, int]] = None
    ) -> Dict[str, Any]:
        """
        Calculate volume state from current and historical volumes
        
        Args:
            symbol: Trading symbol
            current_volume: Current period volume (if available)
            historical_volumes: List of (timestamp_ms, volume) tuples
            lookback_periods: Dict of {"1m": 60, "5m": 300, "15m": 900} (seconds)
        
        Returns:
            Volume state dict:
            {
                "vol_1m": float | None,
                "vol_5m": float | None,
                "vol_15m": float | None,
                "rel_volume": float | None,  # current / avg
                "volume_trend": "INCREASING" | "DECREASING" | "FLAT" | None
            }
        """
        # Default lookback periods
        if lookback_periods is None:
            lookback_periods = {
                "1m": 60,
                "5m": 300,
                "15m": 900
            }
        
        # Graceful degradation if no data
        if historical_volumes is None or len(historical_volumes) == 0:
            self.logger.debug(f"No historical volume data for {symbol}, returning None state")
            return {
                "vol_1m": None,
                "vol_5m": None,
                "vol_15m": None,
                "rel_volume": None,
                "volume_trend": None
            }
        
        try:
            # Get current timestamp (use most recent historical if current not provided)
            now_ms = historical_volumes[-1][0] if historical_volumes else 0
            
            # Calculate rolling volumes for each period
            vol_1m = self._calculate_rolling_volume(
                historical_volumes, 
                now_ms, 
                lookback_periods["1m"]
            )
            vol_5m = self._calculate_rolling_volume(
                historical_volumes, 
                now_ms, 
                lookback_periods["5m"]
            )
            vol_15m = self._calculate_rolling_volume(
                historical_volumes, 
                now_ms, 
                lookback_periods["15m"]
            )
            
            # Calculate relative volume (current vs average)
            rel_volume = None
            if current_volume is not None and vol_5m is not None and vol_5m > 0:
                rel_volume = current_volume / vol_5m
            
            # Detect volume trend
            volume_trend = self._detect_volume_trend(vol_1m, vol_5m, vol_15m)
            
            return {
                "vol_1m": vol_1m,
                "vol_5m": vol_5m,
                "vol_15m": vol_15m,
                "rel_volume": rel_volume,
                "volume_trend": volume_trend
            }
        
        except Exception as e:
            self.logger.error(f"Volume calculation error for {symbol}: {e}", exc_info=True)
            return {
                "vol_1m": None,
                "vol_5m": None,
                "vol_15m": None,
                "rel_volume": None,
                "volume_trend": None
            }
    
    def _calculate_rolling_volume(
        self,
        historical_volumes: List[Tuple[int, float]],
        now_ms: int,
        lookback_seconds: int
    ) -> Optional[float]:
        """
        Calculate rolling volume over lookback period
        
        Args:
            historical_volumes: List of (timestamp_ms, volume)
            now_ms: Current timestamp in milliseconds
            lookback_seconds: Lookback period in seconds
        
        Returns:
            Average volume or None
        """
        lookback_ms = lookback_seconds * 1000
        cutoff_ms = now_ms - lookback_ms
        
        # Filter volumes within lookback window
        relevant_volumes = [
            vol for ts, vol in historical_volumes
            if ts >= cutoff_ms
        ]
        
        if not relevant_volumes:
            return None
        
        return sum(relevant_volumes) / len(relevant_volumes)
    
    def _detect_volume_trend(
        self,
        vol_1m: Optional[float],
        vol_5m: Optional[float],
        vol_15m: Optional[float]
    ) -> Optional[str]:
        """
        Detect volume trend from rolling volumes
        
        Logic:
        - INCREASING: vol_1m > vol_5m > vol_15m (with >10% thresholds)
        - DECREASING: vol_1m < vol_5m < vol_15m (with >10% thresholds)
        - FLAT: within ±10% band
        
        Args:
            vol_1m: 1-minute rolling volume
            vol_5m: 5-minute rolling volume
            vol_15m: 15-minute rolling volume
        
        Returns:
            "INCREASING" | "DECREASING" | "FLAT" | None
        """
        # Need all three to detect trend
        if vol_1m is None or vol_5m is None or vol_15m is None:
            return None
        
        # Avoid division by zero
        if vol_5m == 0 or vol_15m == 0:
            return "FLAT"
        
        # Calculate ratios
        ratio_1m_5m = vol_1m / vol_5m
        ratio_5m_15m = vol_5m / vol_15m
        
        # Thresholds (10% change)
        threshold = 0.10
        
        # INCREASING: both ratios > 1 + threshold
        if ratio_1m_5m > (1 + threshold) and ratio_5m_15m > (1 + threshold):
            return "INCREASING"
        
        # DECREASING: both ratios < 1 - threshold
        if ratio_1m_5m < (1 - threshold) and ratio_5m_15m < (1 - threshold):
            return "DECREASING"
        
        # Otherwise FLAT
        return "FLAT"
