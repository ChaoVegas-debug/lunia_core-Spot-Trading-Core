"""
Phase 8.3: Market Enrichment Layer Tests
Comprehensive test suite for all enrichment engines
"""
import time
import unittest
from unittest.mock import Mock, MagicMock
from typing import List, Tuple

# Test imports
# from lunia_core.app.services.market_enrichment import (
#     VolumeEngine,
#     VolatilityEngine,
#     RegimeDetector,
#     LiquidityStressDetector,
#     MarketStateAggregator
# )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 1: Volume Calculations Correctness
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestVolumeEngine(unittest.TestCase):
    """Test VolumeEngine rolling calculations and trend detection"""
    
    def test_rolling_volume_calculation(self):
        """Test rolling volume averages are calculated correctly"""
        from lunia_core.app.services.market_enrichment import VolumeEngine
        
        engine = VolumeEngine()
        
        # Create test data: increasing volume over time
        now_ms = int(time.time() * 1000)
        historical_volumes: List[Tuple[int, float]] = [
            (now_ms - (i * 1000), 100.0 + i)  # Volume increases with time
            for i in range(900, 0, -1)  # 900 seconds = 15 minutes
        ]
        
        volume_state = engine.calculate_volume_state(
            symbol="BTC/USDT",
            current_volume=200.0,
            historical_volumes=historical_volumes
        )
        
        # Verify all window periods calculated
        assert volume_state["vol_1m"] is not None
        assert volume_state["vol_5m"] is not None
        assert volume_state["vol_15m"] is not None
        
        # Verify trend detected
        assert volume_state["volume_trend"] in ["INCREASING", "DECREASING", "FLAT"]
        
        print(f"✅ TEST 1A PASSED: Volume rolling calculations work")
 
    def test_volume_trend_detection(self):
        """Test volume trend detection logic"""
        from lunia_core.app.services.market_enrichment import VolumeEngine
        
        engine = VolumeEngine()
        
        # Test INCREASING trend: vol_1m > vol_5m > vol_15m
        trend = engine._detect_volume_trend(vol_1m=150.0, vol_5m=120.0, vol_15m=100.0)
        assert trend == "INCREASING"
        
        # Test DECREASING trend: vol_1m < vol_5m < vol_15m
        trend = engine._detect_volume_trend(vol_1m=100.0, vol_5m=120.0, vol_15m=150.0)
        assert trend == "DECREASING"
        
        # Test FLAT: within threshold
        trend = engine._detect_volume_trend(vol_1m=105.0, vol_5m=100.0, vol_15m=98.0)
        assert trend == "FLAT"
        
        print("✅ TEST 1B PASSED: Volume trend detection works")
    
    def test_graceful_degradation(self):
        """Test graceful degradation when no data available"""
        from lunia_core.app.services.market_enrichment import VolumeEngine
        
        engine = VolumeEngine()
        
        volume_state = engine.calculate_volume_state(
            symbol="BTC/USDT",
            historical_volumes=None  # No data
        )
        
        # All fields should be None
        assert volume_state["vol_1m"] is None
        assert volume_state["vol_5m"] is None
        assert volume_state["vol_15m"] is None
        assert volume_state["rel_volume"] is None
        assert volume_state["volume_trend"] is None
        
        print("✅ TEST 1C PASSED: Volume engine graceful degradation works")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 2: ATR & Volatility Regime Classification
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestVolatilityEngine(unittest.TestCase):
    """Test ATR calculation and regime classification"""
    
    def test_atr_calculation(self):
        """Test ATR calculation from candles"""
        from lunia_core.app.services.market_enrichment import VolatilityEngine
        
        engine = VolatilityEngine(atr_period=14)
        
        # Create test candles with known ATR
        candles = [
            {"high": 100.0 + i, "low": 99.0 + i, "close": 99.5 + i}
            for i in range(20)
        ]
        
        volatility_state = engine.calculate_volatility_state(
            symbol="BTC/USDT",
            recent_candles=candles,
            current_price=110.0
        )
        
        # Verify ATR calculated
        assert volatility_state["atr"] is not None
        assert volatility_state["atr"] > 0
        
        # Verify ATR percentage calculated
        assert volatility_state["atr_pct"] is not None
        
        # Verify regime classified
        assert volatility_state["vol_regime"] in ["LOW", "NORMAL", "HIGH", "EXTREME"]
        
        print("✅ TEST 2A PASSED: ATR calculation works")
    
    def test_volatility_regime_classification(self):
        """Test volatility regime thresholds"""
        from lunia_core.app.services.market_enrichment import VolatilityEngine
        
        engine = VolatilityEngine()
        
        # Test LOW regime
        regime = engine._classify_regime(atr_pct=0.3)
        assert regime == "LOW"
        
        # Test NORMAL regime
        regime = engine._classify_regime(atr_pct=1.0)
        assert regime == "NORMAL"
        
        # Test HIGH regime
        regime = engine._classify_regime(atr_pct=2.0)
        assert regime == "HIGH"
        
        # Test EXTREME regime
        regime = engine._classify_regime(atr_pct=5.0)
        assert regime == "EXTREME"
        
        print("✅ TEST 2B PASSED: Volatility regime classification works")
    
    def test_spread_fallback(self):
        """Test spread-based fallback when candles unavailable"""
        from lunia_core.app.services.market_enrichment import VolatilityEngine
        
        engine = VolatilityEngine()
        
        volatility_state = engine.calculate_volatility_state(
            symbol="BTC/USDT",
            recent_candles=None,  # No candles
            fallback_spread_pct=0.001  # 0.1% spread
        )
        
        # Should use fallback
        assert volatility_state["atr"] is None
        assert volatility_state["atr_pct"] is not None
        assert volatility_state["vol_regime"] is not None
        
        print("✅ TEST 2C PASSED: Spread-based fallback works")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 3: Regime Detection Determinism
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestRegimeDetector(unittest.TestCase):
    """Test regime detection determinism and correctness"""
    
    def test_determinism(self):
        """Test that same inputs produce same regime"""
        from lunia_core.app.services.market_enrichment import RegimeDetector
        
        detector = RegimeDetector(lookback_periods=20)
        
        # Trending prices
        prices = [100.0 + i * 0.5 for i in range(30)]
        atr = 2.0
        
        # Run twice
        regime1 = detector.detect_regime("BTC/USDT", prices, atr)
        regime2 = detector.detect_regime("BTC/USDT", prices, atr)
        
        # Should be identical
        assert regime1["regime"] == regime2["regime"]
        assert regime1["confidence"] == regime2["confidence"]
        
        print("✅ TEST 3A PASSED: Regime detection is deterministic")
    
    def test_trend_detection(self):
        """Test TREND regime detection"""
        from lunia_core.app.services.market_enrichment import RegimeDetector
        
        detector = RegimeDetector()
        
        # Strong uptrend
        prices = [100.0 + i * 2.0 for i in range(30)]
        atr = 1.0
        
        regime_state = detector.detect_regime("BTC/USDT", prices, atr)
        
        assert regime_state["regime"] == "TREND"
        assert regime_state["confidence"] > 0.5
        
        print("✅ TEST 3B PASSED: TREND detection works")
    
    def test_range_detection(self):
        """Test RANGE regime detection"""
        from lunia_core.app.services.market_enrichment import RegimeDetector
        
        detector = RegimeDetector()
        
        # Ranging prices (oscillating around 100)
        prices = [100.0 + (i % 2) * 0.5 for i in range(30)]
        atr = 1.0
        
        regime_state = detector.detect_regime("BTC/USDT", prices, atr)
        
        # Should detect RANGE or CHOP
        assert regime_state["regime"] in ["RANGE", "CHOP"]
        
        print("✅ TEST 3C PASSED: RANGE detection works")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 4: Liquidity Stress Detection
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestLiquidityStressDetector(unittest.TestCase):
    """Test liquidity stress classification"""
    
    def test_normal_stress(self):
        """Test NORMAL liquidity conditions"""
        from lunia_core.app.services.market_enrichment import LiquidityStressDetector
        
        detector = LiquidityStressDetector(
            baseline_spread_pct=0.10,
            baseline_depth=100.0
        )
        
        liquidity_state = detector.calculate_liquidity_state(
            symbol="BTC/USDT",
            bid=50000.0,
            ask=50005.0,  # 5 USD spread = 0.01% = normal
            mid_price=50002.5,
            orderbook_bids=[{"price": 50000, "amount": 50} for _ in range(5)],
            orderbook_asks=[{"price": 50005, "amount": 50} for _ in range(5)],
            imbalance=0.0
        )
        
        assert liquidity_state["liquidity_stress"] == "NORMAL"
        
        print("✅ TEST 4A PASSED: NORMAL liquidity stress detected")
    
    def test_warning_stress(self):
        """Test WARNING liquidity conditions"""
        from lunia_core.app.services.market_enrichment import LiquidityStressDetector
        
        detector = LiquidityStressDetector(
            baseline_spread_pct=0.10,
            baseline_depth=100.0
        )
        
        liquidity_state = detector.calculate_liquidity_state(
            symbol="BTC/USDT",
            bid=50000.0,
            ask=50150.0,  # 150 USD spread = 0.3% = warning
            mid_price=50075.0,
            orderbook_bids=[{"price": 50000, "amount": 20} for _ in range(5)],
            orderbook_asks=[{"price": 50150, "amount": 20} for _ in range(5)],
            imbalance=0.0
        )
        
        assert liquidity_state["liquidity_stress"] in ["WARNING", "CRITICAL"]
        
        print("✅ TEST 4B PASSED: WARNING/CRITICAL liquidity stress detected")
    
    def test_critical_stress(self):
        """Test CRITICAL liquidity conditions"""
        from lunia_core.app.services.market_enrichment import LiquidityStressDetector
        
        detector = LiquidityStressDetector(
            baseline_spread_pct=0.10,
            baseline_depth=100.0
        )
        
        liquidity_state = detector.calculate_liquidity_state(
            symbol="BTC/USDT",
            bid=50000.0,
            ask=51000.0,  # 1000 USD spread = 2% = critical
            mid_price=50500.0,
            orderbook_bids=[{"price": 50000, "amount": 5} for _ in range(5)],  # Low depth
            orderbook_asks=[{"price": 51000, "amount": 5} for _ in range(5)],
            imbalance=0.0
        )
        
        assert liquidity_state["liquidity_stress"] == "CRITICAL"
        
        print("✅ TEST 4C PASSED: CRITICAL liquidity stress detected")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 5: Market State Aggregation Correctness
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestMarketStateAggregator(unittest.TestCase):
    """Test market state aggregation"""
    
    def test_aggregation_completeness(self):
        """Test that market_state contains all required fields"""
        from lunia_core.app.services.market_enrichment import MarketStateAggregator
        
        aggregator = MarketStateAggregator()
        
        # Mock snapshot
        mock_snapshot = Mock()
        mock_snapshot.mid_price = 50000.0
        mock_snapshot.bid = 49995.0
        mock_snapshot.ask = 50005.0
        mock_snapshot.bids = []
        mock_snapshot.asks = []
        
        market_state = aggregator.aggregate_market_state(
            symbol="BTC/USDT",
            snapshot=mock_snapshot,
            historical_data=None
        )
        
        # Verify all top-level keys present
        assert "volume" in market_state
        assert "volatility" in market_state
        assert "regime" in market_state
        assert "liquidity" in market_state
        assert "market_risk_flag" in market_state
        assert "timestamp_ms" in market_state
        
        # Verify risk flag is valid
        assert market_state["market_risk_flag"] in ["SAFE", "RISKY", "DANGEROUS", "UNKNOWN"]
        
        print("✅ TEST 5A PASSED: Market state aggregation is complete")
    
    def test_risk_flag_determination(self):
        """Test market risk flag logic"""
        from lunia_core.app.services.market_enrichment import MarketStateAggregator
        
        aggregator = MarketStateAggregator()
        
        # SAFE: LOW vol + NORMAL liquidity
        flag = aggregator._determine_risk_flag(
            {"vol_regime": "LOW"},
            {"liquidity_stress": "NORMAL"}
        )
        assert flag == "SAFE"
        
        # RISKY: HIGH vol + NORMAL liquidity
        flag = aggregator._determine_risk_flag(
            {"vol_regime": "HIGH"},
            {"liquidity_stress": "NORMAL"}
        )
        assert flag == "RISKY"
        
        # DANGEROUS: EXTREME vol
        flag = aggregator._determine_risk_flag(
            {"vol_regime": "EXTREME"},
            {"liquidity_stress": "NORMAL"}
        )
        assert flag == "DANGEROUS"
        
        # DANGEROUS: CRITICAL liquidity
        flag = aggregator._determine_risk_flag(
            {"vol_regime": "NORMAL"},
            {"liquidity_stress": "CRITICAL"}
        )
        assert flag == "DANGEROUS"
        
        print("✅ TEST 5B PASSED: Risk flag determination works")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 6: Missing Data Graceful Degradation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestGracefulDegradation(unittest.TestCase):
    """Test all engines handle missing data gracefully"""
    
    def test_all_engines_degrade_gracefully(self):
        """Test that all engines return None fields when data missing"""
        from lunia_core.app.services.market_enrichment import (
            VolumeEngine,
            VolatilityEngine,
            RegimeDetector,
            LiquidityStressDetector
        )
        
        # Volume engine
        vol_engine = VolumeEngine()
        vol_state = vol_engine.calculate_volume_state("BTC/USDT", historical_volumes=None)
        assert all(v is None for v in vol_state.values())
        
        # Volatility engine
        volatility_engine = VolatilityEngine()
        volatility_state = volatility_engine.calculate_volatility_state(
            "BTC/USDT",
            recent_candles=None,
            fallback_spread_pct=None
        )
        assert all(v is None for v in volatility_state.values())
        
        # Regime detector
        regime_detector = RegimeDetector()
        regime_state = regime_detector.detect_regime("BTC/USDT", recent_prices=None)
        assert regime_state["regime"] is None
        
        # Liquidity detector
        liquidity_detector = LiquidityStressDetector()
        liquidity_state = liquidity_detector.calculate_liquidity_state(
            "BTC/USDT",
            bid=None,
            ask=None
        )
        # Should have at least imbalance as None (passed through)
        assert liquidity_state["spread_pct"] is None
        
        print("✅ TEST 6 PASSED: All engines degrade gracefully")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 7: Performance Sanity (<5ms per enrichment)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestPerformance(unittest.TestCase):
    """Test enrichment performance"""
    
    def test_aggregation_performance(self):
        """Test that full enrichment completes in <5ms p95"""
        from lunia_core.app.services.market_enrichment import MarketStateAggregator
        
        aggregator = MarketStateAggregator()
        
        # Mock snapshot
        mock_snapshot = Mock()
        mock_snapshot.mid_price = 50000.0
        mock_snapshot.bid = 49995.0
        mock_snapshot.ask = 50005.0
        mock_snapshot.bids = []
        mock_snapshot.asks = []
        
        # Benchmark 100 runs
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            market_state = aggregator.aggregate_market_state(
                symbol="BTC/USDT",
                snapshot=mock_snapshot,
                historical_data=None
            )
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)
        
        # Calculate p95
        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]
        
        print(f"Market enrichment latency p95: {p95:.2f}ms")
        
        # Assert p95 < 5ms
        assert p95 < 5.0, f"p95 latency {p95:.2f}ms exceeds 5ms"
        
        print(f"✅ TEST 7 PASSED: Performance p95 = {p95:.2f}ms")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 8: Integration (market_state in AI Context)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestIntegration(unittest.TestCase):
    """Test integration with PulseWorker/AIGateway"""
    
    def test_market_state_format_for_ai(self):
        """Test that market_state is properly formatted for AI Gateway"""
        from lunia_core.app.services.market_enrichment import MarketStateAggregator
        
        aggregator = MarketStateAggregator()
        
        # Mock snapshot
        mock_snapshot = Mock()
        mock_snapshot.mid_price = 50000.0
        mock_snapshot.bid = 49995.0
        mock_snapshot.ask = 50005.0
        mock_snapshot.bids = []
        mock_snapshot.asks = []
        
        market_state = aggregator.aggregate_market_state(
            symbol="BTC/USDT",
            snapshot=mock_snapshot,
            historical_data=None
        )
        
        # Verify market_state is JSON-serializable (for DB persistence)
        import json
        try:
            json_str = json.dumps(market_state)
            assert len(json_str) > 0
        except Exception as e:
            raise AssertionError(f"market_state not JSON-serializable: {e}")
        
        # Verify structure matches expected AI context format
        assert isinstance(market_state["volume"], dict)
        assert isinstance(market_state["volatility"], dict)
        assert isinstance(market_state["regime"], dict)
        assert isinstance(market_state["liquidity"], dict)
        assert isinstance(market_state["market_risk_flag"], str)
        assert isinstance(market_state["timestamp_ms"], int)
        
        print("✅ TEST 8 PASSED: market_state format valid for AI Gateway")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST SUITE RUNNER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    # Run all tests
    unittest.main(verbosity=2)
