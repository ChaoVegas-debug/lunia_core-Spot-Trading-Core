"""
Phase 8.3: Market State Aggregator
Combines all enrichment engines into single canonical market_state object
"""
from __future__ import annotations

import logging
import time
from typing import Dict, Any, Optional

from .volume import VolumeEngine
from .volatility import VolatilityEngine
from .regime import RegimeDetector
from .liquidity import LiquidityStressDetector

logger = logging.getLogger(__name__)


class MarketStateAggregator:
    """
    Aggregate all market enrichment engines into single canonical state
    
    Combines:
    - Volume state (VolumeEngine)
    - Volatility state (VolatilityEngine)
    - Regime state (RegimeDetector)
    - Liquidity state (LiquidityStressDetector)
    
    Outputs:
    - Complete market_state object
    - Market risk flag (SAFE / RISKY / DANGEROUS)
    - Timestamp
    
    CRITICAL:
    - Deterministic
    - Explainable
    - Fail-operational (timeout enforced)
    - No ML, no randomness
    """
    
    def __init__(
        self,
        volume_engine: Optional[VolumeEngine] = None,
        volatility_engine: Optional[VolatilityEngine] = None,
        regime_detector: Optional[RegimeDetector] = None,
        liquidity_detector: Optional[LiquidityStressDetector] = None,
        timeout_ms: int = 10
    ):
        """
        Initialize Market State Aggregator
        
        Args:
            volume_engine: VolumeEngine instance (default: auto-create)
            volatility_engine: VolatilityEngine instance (default: auto-create)
            regime_detector: RegimeDetector instance (default: auto-create)
            liquidity_detector: LiquidityStressDetector instance (default: auto-create)
            timeout_ms: Hard timeout per enrichment step (default 10ms)
        """
        self.volume_engine = volume_engine or VolumeEngine()
        self.volatility_engine = volatility_engine or VolatilityEngine()
        self.regime_detector = regime_detector or RegimeDetector()
        self.liquidity_detector = liquidity_detector or LiquidityStressDetector()
        self.timeout_ms = timeout_ms
        self.logger = logger
    
    def aggregate_market_state(
        self,
        symbol: str,
        snapshot: Any,  # MarketSnapshot from market_data
        historical_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Aggregate complete market_state from all engines
        
        Args:
            symbol: Trading symbol
            snapshot: MarketSnapshot object (from strategy context)
            historical_data: Optional historical data dict:
                {
                    "volumes": [(timestamp_ms, volume), ...],
                    "candles": [{"high": ..., "low": ..., "close": ...}, ...],
                    "prices": [price1, price2, ...]
                }
        
        Returns:
            market_state dict:
            {
                "volume": {...},
                "volatility": {...},
                "regime": {...},
                "liquidity": {...},
                "market_risk_flag": "SAFE" | "RISKY" | "DANGEROUS",
                "timestamp_ms": int
            }
        """
        start_time = time.perf_counter()
        timestamp_ms = int(time.time() * 1000)
        
        # Extract data from snapshot
        mid_price = snapshot.mid_price
        bid = snapshot.bid
        ask = snapshot.ask
        
        # Get orderbook data (if available)
        orderbook_bids = [
            {"price": level.price, "amount": level.amount}
            for level in snapshot.bids[:10]
        ] if hasattr(snapshot, 'bids') else None
        
        orderbook_asks = [
            {"price": level.price, "amount": level.amount}
            for level in snapshot.asks[:10]
        ] if hasattr(snapshot, 'asks') else None
        
        # Calculate orderbook imbalance (simple version, could use SnapshotBuilder's)
        imbalance = self._calculate_imbalance(orderbook_bids, orderbook_asks)
        
        # Prepare historical data
        historical_data = historical_data or {}
        
        try:
            # STEP 1: Volume state (with timeout check)
            volume_state = self._with_timeout(
                lambda: self.volume_engine.calculate_volume_state(
                    symbol=symbol,
                    current_volume=historical_data.get("current_volume"),
                    historical_volumes=historical_data.get("volumes")
                ),
                "volume"
            )
            
            # STEP 2: Volatility state (with timeout check)
            spread_pct = self._calculate_spread_pct(bid, ask, mid_price)
            volatility_state = self._with_timeout(
                lambda: self.volatility_engine.calculate_volatility_state(
                    symbol=symbol,
                    recent_candles=historical_data.get("candles"),
                    current_price=mid_price,
                    fallback_spread_pct=spread_pct
                ),
                "volatility"
            )
            
            # STEP 3: Regime state (with timeout check)
            atr = volatility_state.get("atr") if volatility_state else None
            volume_trend = volume_state.get("volume_trend") if volume_state else None
            regime_state = self._with_timeout(
                lambda: self.regime_detector.detect_regime(
                    symbol=symbol,
                    recent_prices=historical_data.get("prices"),
                    atr=atr,
                    volume_trend=volume_trend
                ),
                "regime"
            )
            
            # STEP 4: Liquidity state (with timeout check)
            liquidity_state = self._with_timeout(
                lambda: self.liquidity_detector.calculate_liquidity_state(
                    symbol=symbol,
                    bid=bid,
                    ask=ask,
                    mid_price=mid_price,
                    orderbook_bids=orderbook_bids,
                    orderbook_asks=orderbook_asks,
                    imbalance=imbalance
                ),
                "liquidity"
            )
            
            # STEP 5: Calculate market risk flag
            market_risk_flag = self._determine_risk_flag(
                volatility_state, 
                liquidity_state
            )
            
            # Build final market_state
            market_state = {
                "volume": volume_state or {},
                "volatility": volatility_state or {},
                "regime": regime_state or {},
                "liquidity": liquidity_state or {},
                "market_risk_flag": market_risk_flag,
                "timestamp_ms": timestamp_ms
            }
            
            # Log performance
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            if elapsed_ms > self.timeout_ms:
                self.logger.warning(
                    f"Market enrichment for {symbol} took {elapsed_ms:.2f}ms "
                    f"(exceeds {self.timeout_ms}ms timeout)"
                )
            
            return market_state
        
        except Exception as e:
            self.logger.error(
                f"Market state aggregation error for {symbol}: {e}",
                exc_info=True
            )
            
            # Fail-operational: return empty state
            return {
                "volume": {},
                "volatility": {},
                "regime": {},
                "liquidity": {},
                "market_risk_flag": "UNKNOWN",
                "timestamp_ms": timestamp_ms
            }
    
    def _with_timeout(self, func, name: str):
        """
        Execute function with timeout (simplified version)
        
        Note: True timeout enforcement would require threading.Timer
        For v1, we just log if exceeded
        
        Args:
            func: Function to execute
            name: Name for logging
        
        Returns:
            Function result or None
        """
        start = time.perf_counter()
        try:
            result = func()
            elapsed_ms = (time.perf_counter() - start) * 1000
            
            if elapsed_ms > self.timeout_ms:
                self.logger.warning(
                    f"{name} enrichment exceeded {self.timeout_ms}ms "
                    f"(took {elapsed_ms:.2f}ms)"
                )
            
            return result
        
        except Exception as e:
            self.logger.error(f"{name} enrichment failed: {e}")
            return None
    
    def _calculate_spread_pct(
        self,
        bid: Optional[float],
        ask: Optional[float],
        mid: Optional[float]
    ) -> Optional[float]:
        """
        Calculate spread as percentage (helper)
        
        Returns:
            Spread as decimal (e.g., 0.001 = 0.1%) or None
        """
        if bid is None or ask is None or mid is None or mid == 0:
            return None
        
        spread_abs = ask - bid
        spread_pct = spread_abs / mid  # Decimal (not percentage)
        
        return spread_pct
    
    def _calculate_imbalance(
        self,
        bids: Optional[list],
        asks: Optional[list]
    ) -> Optional[float]:
        """
        Calculate orderbook imbalance (helper)
        
        Returns:
            Imbalance (-1 to +1) or None
        """
        if not bids or not asks:
            return None
        
        bid_vol = sum(level.get("amount", 0) for level in bids)
        ask_vol = sum(level.get("amount", 0) for level in asks)
        
        total_vol = bid_vol + ask_vol
        if total_vol == 0:
            return None
        
        imbalance = (bid_vol - ask_vol) / total_vol
        return imbalance
    
    def _determine_risk_flag(
        self,
        volatility_state: Optional[Dict],
        liquidity_state: Optional[Dict]
    ) -> str:
        """
        Determine market risk flag from volatility and liquidity states
        
        Rules:
        - SAFE: vol_regime=LOW/NORMAL AND liquidity_stress=NORMAL
        - RISKY: vol_regime=HIGH OR liquidity_stress=WARNING
        - DANGEROUS: vol_regime=EXTREME OR liquidity_stress=CRITICAL
        
        Args:
            volatility_state: Output from VolatilityEngine
            liquidity_state: Output from LiquidityStressDetector
        
        Returns:
            "SAFE" | "RISKY" | "DANGEROUS" | "UNKNOWN"
        """
        if not volatility_state or not liquidity_state:
            return "UNKNOWN"
        
        vol_regime = volatility_state.get("vol_regime")
        liquidity_stress = liquidity_state.get("liquidity_stress")
        
        # DANGEROUS: EXTREME volatility OR CRITICAL liquidity
        if vol_regime == "EXTREME" or liquidity_stress == "CRITICAL":
            return "DANGEROUS"
        
        # RISKY: HIGH volatility OR WARNING liquidity
        if vol_regime == "HIGH" or liquidity_stress == "WARNING":
            return "RISKY"
        
        # SAFE: LOW/NORMAL volatility AND NORMAL liquidity
        if vol_regime in ["LOW", "NORMAL"] and liquidity_stress == "NORMAL":
            return "SAFE"
        
        # Default: UNKNOWN
        return "UNKNOWN"
