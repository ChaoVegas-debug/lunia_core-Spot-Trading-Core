"""
Phase 8.3: Volatility Engine (Market Context)
ATR calculation and volatility regime classification

CRITICAL: This is for MARKET ENRICHMENT, not risk limits.
Different from risk/providers/volatility.py (which provides annualized volatility for position sizing)
"""
from __future__ import annotations

import logging
import math
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class VolatilityEngine:
    """
    Calculate intraday ATR and classify volatility regime
    
    Provides:
    - ATR (Average True Range) - 14 period default
    - ATR as percentage of price
    - Volatility regime classification (LOW / NORMAL / HIGH / EXTREME)
    
    This is MARKET CONTEXT volatility, not portfolio risk volatility.
    """
    
    def __init__(self, atr_period: int = 14):
        """
        Initialize Volatility Engine
        
        Args:
            atr_period: ATR calculation period (default 14)
        """
        self.atr_period = atr_period
        self.logger = logger
    
    def calculate_volatility_state(
        self,
        symbol: str,
        recent_candles: Optional[List[Dict[str, float]]] = None,
        current_price: Optional[float] = None,
        fallback_spread_pct: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calculate volatility state from recent candles or fallback to spread
        
        Args:
            symbol: Trading symbol
            recent_candles: List of OHLC candles [{"high": ..., "low": ..., "close": ...}, ...]
            current_price: Current price (for ATR percentage calculation)
            fallback_spread_pct: Fallback spread-based proxy if candles unavailable
        
        Returns:
            Volatility state dict:
            {
                "atr": float | None,
                "atr_pct": float | None,
                "vol_regime": "LOW" | "NORMAL" | "HIGH" | "EXTREME" | None
            }
        """
        # Try ATR calculation if candles available
        if recent_candles and len(recent_candles) >= self.atr_period:
            try:
                atr = self._calculate_atr(recent_candles)
                
                # Calculate ATR as percentage of price
                atr_pct = None
                if atr is not None and current_price is not None and current_price > 0:
                    atr_pct = (atr / current_price) * 100  # Convert to percentage
                
                # Classify regime
                vol_regime = self._classify_regime(atr_pct)
                
                return {
                    "atr": atr,
                    "atr_pct": atr_pct,
                    "vol_regime": vol_regime
                }
            
            except Exception as e:
                self.logger.error(f"ATR calculation error for {symbol}: {e}", exc_info=True)
                # Fall through to fallback
        
        # Fallback: use spread as volatility proxy
        if fallback_spread_pct is not None:
            self.logger.debug(f"Using spread-based volatility proxy for {symbol}")
            vol_regime = self._classify_regime(fallback_spread_pct * 100)  # Convert to percentage
            
            return {
                "atr": None,
                "atr_pct": fallback_spread_pct * 100,
                "vol_regime": vol_regime
            }
        
        # No data available
        self.logger.debug(f"No volatility data for {symbol}, returning None state")
        return {
            "atr": None,
            "atr_pct": None,
            "vol_regime": None
        }
    
    def _calculate_atr(self, candles: List[Dict[str, float]]) -> Optional[float]:
        """
        Calculate Average True Range (ATR)
        
        Formula:
        1. True Range (TR) = max(high - low, abs(high - prev_close), abs(low - prev_close))
        2. ATR = EMA(TR, period)
        
        Args:
            candles: List of OHLC dicts with keys: high, low, close
        
        Returns:
            ATR value or None
        """
        if len(candles) < 2:
            return None
        
        try:
            # Calculate True Ranges
            true_ranges = []
            for i in range(1, len(candles)):
                high = candles[i].get("high")
                low = candles[i].get("low")
                prev_close = candles[i-1].get("close")
                
                if high is None or low is None or prev_close is None:
                    continue
                
                # True Range = max(high-low, abs(high-prev_close), abs(low-prev_close))
                tr = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close)
                )
                true_ranges.append(tr)
            
            if len(true_ranges) < self.atr_period:
                return None
            
            # Calculate ATR as simple moving average of True Ranges
            # (could use EMA for smoother results in production)
            atr = sum(true_ranges[-self.atr_period:]) / self.atr_period
            
            return atr
        
        except Exception as e:
            self.logger.error(f"ATR calculation exception: {e}", exc_info=True)
            return None
    
    def _classify_regime(self, atr_pct: Optional[float]) -> Optional[str]:
        """
        Classify volatility regime based on ATR percentage
        
        Thresholds (example, tunable):
        - LOW: atr_pct < 0.5%
        - NORMAL: 0.5% <= atr_pct < 1.5%
        - HIGH: 1.5% <= atr_pct < 3.0%
        - EXTREME: atr_pct >= 3.0%
        
        Args:
            atr_pct: ATR as percentage of price
        
        Returns:
            "LOW" | "NORMAL" | "HIGH" | "EXTREME" | None
        """
        if atr_pct is None:
            return None
        
        # Regime thresholds (percentages)
        LOW_THRESHOLD = 0.5
        NORMAL_THRESHOLD = 1.5
        HIGH_THRESHOLD = 3.0
        
        if atr_pct < LOW_THRESHOLD:
            return "LOW"
        elif atr_pct < NORMAL_THRESHOLD:
            return "NORMAL"
        elif atr_pct < HIGH_THRESHOLD:
            return "HIGH"
        else:
            return "EXTREME"
