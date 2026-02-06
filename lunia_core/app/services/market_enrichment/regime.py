"""
Phase 8.3: Regime Detection
Deterministic regime classification based on price action + ATR
"""
from __future__ import annotations

import logging
import statistics
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class RegimeDetector:
    """
    Deterministic regime classification
    
    Provides:
    - Regime classification: TREND / RANGE / CHOP / BREAKOUT
    - Confidence score (0.0 - 1.0)
    
    Rules (deterministic, explainable):
    - TREND: price slope > 2*ATR over lookback
    - RANGE: price within 1*ATR band for >80% of lookback
    - CHOP: neither TREND nor RANGE (oscillating)
    - BREAKOUT: price breaks ATR band with volume surge
    """
    
    def __init__(self, lookback_periods: int = 20):
        """
        Initialize Regime Detector
        
        Args:
            lookback_periods: Number of periods for regime analysis (default 20)
        """
        self.lookback_periods = lookback_periods
        self.logger = logger
    
    def detect_regime(
        self,
        symbol: str,
        recent_prices: Optional[List[float]] = None,
        atr: Optional[float] = None,
        volume_trend: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Detect market regime from recent prices and ATR
        
        Args:
            symbol: Trading symbol
            recent_prices: List of recent prices (most recent last)
            atr: Average True Range from VolatilityEngine
            volume_trend: Volume trend from VolumeEngine ("INCREASING", etc.)
        
        Returns:
            Regime state dict:
            {
                "regime": "TREND" | "RANGE" | "CHOP" | "BREAKOUT" | None,
                "confidence": float  # 0.0 - 1.0
            }
        """
        # Graceful degradation
        if not recent_prices or len(recent_prices) < self.lookback_periods:
            self.logger.debug(f"Insufficient price data for {symbol}, returning None regime")
            return {
                "regime": None,
                "confidence": 0.0
            }
        
        try:
            # Use most recent lookback_periods prices
            prices = recent_prices[-self.lookback_periods:]
            
            # Calculate price statistics
            price_slope = self._calculate_slope(prices)
            price_range_pct = self._calculate_range_pct(prices)
            range_tightness = self._calculate_range_tightness(prices)
            
            # Detect regime
            regime, confidence = self._classify_regime(
                prices=prices,
                price_slope=price_slope,
                price_range_pct=price_range_pct,
                range_tightness=range_tightness,
                atr=atr,
                volume_trend=volume_trend
            )
            
            return {
                "regime": regime,
                "confidence": confidence
            }
        
        except Exception as e:
            self.logger.error(f"Regime detection error for {symbol}: {e}", exc_info=True)
            return {
                "regime": None,
                "confidence": 0.0
            }
    
    def _calculate_slope(self, prices: List[float]) -> float:
        """
        Calculate price slope (linear regression)
        
        Args:
            prices: List of prices
        
        Returns:
            Slope value (positive = uptrend, negative = downtrend)
        """
        n = len(prices)
        if n < 2:
            return 0.0
        
        # Simple linear regression: slope = covariance(x, y) / variance(x)
        x_values = list(range(n))
        x_mean = statistics.mean(x_values)
        y_mean = statistics.mean(prices)
        
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, prices))
        denominator = sum((x - x_mean) ** 2 for x in x_values)
        
        if denominator == 0:
            return 0.0
        
        slope = numerator / denominator
        return slope
    
    def _calculate_range_pct(self, prices: List[float]) -> float:
        """
        Calculate price range as percentage of mean
        
        Args:
            prices: List of prices
        
        Returns:
            Range percentage
        """
        if not prices:
            return 0.0
        
        price_min = min(prices)
        price_max = max(prices)
        price_mean = statistics.mean(prices)
        
        if price_mean == 0:
            return 0.0
        
        return ((price_max - price_min) / price_mean) * 100
    
    def _calculate_range_tightness(self, prices: List[float]) -> float:
        """
        Calculate how much of time price stayed within tight range
        
        Args:
            prices: List of prices
        
        Returns:
            Tightness score (0.0 - 1.0, higher = tighter range)
        """
        if len(prices) < 2:
            return 0.0
        
        price_mean = statistics.mean(prices)
        price_std = statistics.stdev(prices) if len(prices) > 1 else 0.0
        
        if price_mean == 0:
            return 0.0
        
        # Count how many prices are within 1 std dev
        within_range = sum(
            1 for p in prices 
            if abs(p - price_mean) <= price_std
        )
        
        tightness = within_range / len(prices)
        return tightness
    
    def _classify_regime(
        self,
        prices: List[float],
        price_slope: float,
        price_range_pct: float,
        range_tightness: float,
        atr: Optional[float],
        volume_trend: Optional[str]
    ) -> tuple[str, float]:
        """
        Classify regime based on calculated metrics
        
        Returns:
            (regime, confidence) tuple
        """
        price_mean = statistics.mean(prices)
        
        # Normalize slope by price (to get percentage change per period)
        if price_mean > 0:
            slope_pct = (price_slope / price_mean) * 100
        else:
            slope_pct = 0.0
        
        # Use ATR for thresholds if available
        if atr is not None and price_mean > 0:
            atr_pct = (atr / price_mean) * 100
        else:
            atr_pct = 1.0  # Default threshold
        
        # Rule 1: BREAKOUT (price breaking range + volume surge)
        if price_range_pct > 1.5 * atr_pct and volume_trend == "INCREASING":
            # Recent price is at extreme of range
            recent_price = prices[-1]
            price_max = max(prices)
            price_min = min(prices)
            
            if recent_price == price_max or recent_price == price_min:
                return ("BREAKOUT", 0.85)
        
        # Rule 2: TREND (significant slope > 1.5*ATR for better sensitivity)
        if abs(slope_pct) > 1.5 * atr_pct:
            confidence = min(abs(slope_pct) / (3 * atr_pct), 0.9)
            return ("TREND", confidence)
        
        # Rule 3: RANGE (tight price action, >80% within 1 std dev)
        if range_tightness > 0.8 and price_range_pct < atr_pct:
            confidence = range_tightness
            return ("RANGE", confidence)
        
        # Rule 4: CHOP (neither trend nor range)
        return ("CHOP", 0.6)
