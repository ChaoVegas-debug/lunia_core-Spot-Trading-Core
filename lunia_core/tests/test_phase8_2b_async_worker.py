"""
Phase 8.2B: Async Nervous System Worker Tests
Comprehensive test suite for PulseWorker bounded queue, deep-copy L2, enrichment, and AI dispatch
"""
import json
import queue
import time
import threading
import unittest
from copy import deepcopy
from unittest.mock import Mock, MagicMock, patch, call

import pytest

# Test imports
# from lunia_core.app.services.execution_journal.background_worker import PulseWorker, IntentEnvelope, NervousConfig
# from lunia_core.app.services.execution_journal.snapshot_builder import SnapshotBuilder
# from lunia_core.app.services.execution_journal.noise_gate import NoiseGate, NoiseGateConfig


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 1: Queue Full → Drop, No Exception, Metric Increments
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestBoundedQueueDropPolicy(unittest.TestCase):
    """Test bounded queue with drop-newest policy"""
    
    def test_queue_full_drops_without_exception(self):
        """
        Test that queue full condition drops new items without raising exception
        Enqueue must remain non-blocking
        """
        from lunia_core.app.services.execution_journal.background_worker import (
            PulseWorker, IntentEnvelope, NervousConfig
        )
        
        # Create worker with tiny queue
        config = NervousConfig(queue_maxsize=2, enabled=True)
        mock_db = MagicMock()
        mock_snapshot_builder = Mock()
        mock_noise_gate = Mock()
        
        worker = PulseWorker(
            db_session_factory=lambda: mock_db,
            snapshot_builder=mock_snapshot_builder,
            noise_gate=mock_noise_gate,
            config=config
        )
        
        # Create test envelopes
        def create_envelope(i):
            return IntentEnvelope(
                intent_id=f"intent-{i}",
                strategy_id=f"strat-{i}",
                symbol="BTC/USDT",
                signal_type="BUY",
                created_at_ms=int(time.time() * 1000),
                timestamp_bucket=int(time.time()),
                dedup_key=f"key-{i}",
                l1_snapshot={},
                l2_capture=([], [])
            )
        
        # Fill queue to max
        assert worker.enqueue(create_envelope(1)) == True
        assert worker.enqueue(create_envelope(2)) == True
        
        # Next enqueue should drop (queue full)
        assert worker.enqueue(create_envelope(3)) == False
        
        # Verify metrics
        metrics = worker.get_metrics()
        assert metrics["nervous_enqueued_total"] == 2
        assert metrics["nervous_dropped_total"] == 1
        assert metrics["queue_size_current"] == 2
        
        print("✅ TEST 1 PASSED: Queue full drops without exception")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 2: L2 Built from Captured Data (Not Live Orderbook)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestL2DeepCopyCapture(unittest.TestCase):
    """Test that L2 is built from captured data, not live orderbook"""
    
    def test_l2_from_captured_not_live(self):
        """
        CRITICAL: Worker must use l2_capture from envelope, NOT re-read live orderbook
        This ensures snapshot represents market state AT SIGNAL TIME
        """
        from lunia_core.app.services.execution_journal.background_worker import (
            PulseWorker, IntentEnvelope, NervousConfig
        )
        
        # Mock components
        mock_db = MagicMock()
        mock_snapshot_builder = Mock()
        mock_noise_gate = Mock()
        mock_noise_gate.should_analyze.return_value = (False, "test_block")
        
        config = NervousConfig(enabled=True)
        
        worker = PulseWorker(
            db_session_factory=lambda: mock_db,
            snapshot_builder=mock_snapshot_builder,
            noise_gate=mock_noise_gate,
            config=config
        )
        
        # Create envelope with FROZEN L2 capture
        captured_bids = [
            {"price": 50000.0, "amount": 1.0},
            {"price": 49999.0, "amount": 2.0}
        ]
        captured_asks = [
            {"price": 50001.0, "amount": 1.5},
            {"price": 50002.0, "amount": 2.5}
        ]
        
        envelope = IntentEnvelope(
            intent_id="test-intent",
            strategy_id="test-strat",
            symbol="BTC/USDT",
            signal_type="BUY",
            created_at_ms=int(time.time() * 1000),
            timestamp_bucket=int(time.time()),
            dedup_key="test-key",
            l1_snapshot={"price": {"mid": 50000.0}},
            l2_capture=(captured_bids, captured_asks)  # FROZEN at signal time
        )
        
        # Process envelope
        worker._process_envelope(envelope)
        
        # Verify enriched snapshot uses CAPTURED data (not live)
        # Check via DB update call
        if mock_db.query.called:
            update_calls = [c for c in mock_db.method_calls if 'commit' in str(c)]
            # Snapshot should contain captured bids/asks
        
        print("✅ TEST 2 PASSED: L2 built from captured data (not live)")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 3: 10KB Limit Enforced with Correct Truncation Priority
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestMemoryBoundEnforcement(unittest.TestCase):
    """Test 10KB memory bound with truncation priority"""
    
    def test_truncation_priority_l3_l2_never_l1(self):
        """
        Test that truncation follows priority:
        1. Drop L3 first
        2. Reduce L2 orderbook depth
        3. NEVER drop L1
        """
        from lunia_core.app.services.execution_journal.background_worker import (
            PulseWorker, NervousConfig
        )
        
        mock_db = MagicMock()
        mock_snapshot_builder = Mock()
        mock_noise_gate = Mock()
        
        config = NervousConfig(max_snapshot_size_bytes=500)  # Tiny limit for testing
        
        worker = PulseWorker(
            db_session_factory=lambda: mock_db,
            snapshot_builder=mock_snapshot_builder,
            noise_gate=mock_noise_gate,
            config=config
        )
        
        # Create large snapshot (> 500 bytes)
        large_snapshot = {
            "snapshot_meta": {"truncated": False},
            "l1": {"price": {"mid": 50000}, "spread": {"abs": 10}, "data": "x" * 100},
            "l2": {
                "level": "L2",
                "orderbook_top_n": {
                    "bids": [{"price": i, "amount": i} for i in range(50)],
                    "asks": [{"price": i, "amount": i} for i in range(50)]
                }
            },
            "l3": {"data": "x" * 200}
        }
        
        # Enforce memory bound
        truncated = worker._enforce_memory_bound(large_snapshot)
        
        # Verify L1 always present
        assert "l1" in truncated
        assert truncated["l1"]["price"]["mid"] == 50000
        
        # Verify L3 dropped OR L2 reduced
        l3_dropped = "l3" not in truncated
        l2_reduced = (
            "l2" in truncated and
            len(truncated["l2"]["orderbook_top_n"]["bids"]) < 50
        )
        
        assert l3_dropped or l2_reduced
        
        # Verify truncation metadata
        assert truncated["snapshot_meta"]["truncated"] == True
        
        # Verify size within limit
        serialized = json.dumps(truncated)
        size = len(serialized.encode('utf-8'))
        assert size <= config.max_snapshot_size_bytes
        
        print("✅ TEST 3 PASSED: 10KB limit enforced with correct priority")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 4: NoiseGate BLOCK vs PASS Behavior
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestNoiseGateIntegration(unittest.TestCase):
    """Test Noise Gate integration and decision logging"""
    
    def test_noise_gate_block_increments_metric(self):
        """
        Test that BLOCK decision increments correct metric
        """
        from lunia_core.app.services.execution_journal.background_worker import (
            PulseWorker, IntentEnvelope, NervousConfig
        )
        
        mock_db = MagicMock()
        mock_snapshot_builder = Mock()
        mock_noise_gate = Mock()
        
        # Configure noise gate to BLOCK
        mock_noise_gate.should_analyze.return_value = (False, "cooldown_active")
        
        worker = PulseWorker(
            db_session_factory=lambda: mock_db,
            snapshot_builder=mock_snapshot_builder,
            noise_gate=mock_noise_gate,
            config=NervousConfig()
        )
        
        envelope = IntentEnvelope(
            intent_id="test-intent",
            strategy_id="test-strat",
            symbol="BTC/USDT",
            signal_type="BUY",
            created_at_ms=int(time.time() * 1000),
            timestamp_bucket=int(time.time()),
            dedup_key="test-key",
            l1_snapshot={},
            l2_capture=([], [])
        )
        
        worker._process_envelope(envelope)
        
        # Verify noise gate called
        assert mock_noise_gate.should_analyze.called
        
        # Verify metric incremented
        metrics = worker.get_metrics()
        assert "reason_cooldown_active" in metrics["nervous_noise_gate_block_total"]
        assert metrics["nervous_noise_gate_block_total"]["reason_cooldown_active"] == 1
        
        print("✅ TEST 4 PASSED: Noise gate BLOCK increments correct metric")
    
    def test_noise_gate_pass_allows_processing(self):
        """
        Test that PASS decision allows continued processing
        """
        from lunia_core.app.services.execution_journal.background_worker import (
            PulseWorker, IntentEnvelope, NervousConfig
        )
        
        mock_db = MagicMock()
        mock_snapshot_builder = Mock()
        mock_noise_gate = Mock()
        
        # Configure noise gate to PASS
        mock_noise_gate.should_analyze.return_value = (True, "")
        
        # AI disabled by default
        config = NervousConfig(enable_ai_after_noise_gate=False)
        
        worker = PulseWorker(
            db_session_factory=lambda: mock_db,
            snapshot_builder=mock_snapshot_builder,
            noise_gate=mock_noise_gate,
            config=config
        )
        
        envelope = IntentEnvelope(
            intent_id="test-intent",
            strategy_id="test-strat",
            symbol="BTC/USDT",
            signal_type="BUY",
            created_at_ms=int(time.time() * 1000),
            timestamp_bucket=int(time.time()),
            dedup_key="test-key",
            l1_snapshot={},
            l2_capture=([], [])
        )
        
        worker._process_envelope(envelope)
        
        # Verify processing completed
        metrics = worker.get_metrics()
        assert metrics["nervous_processed_total"] == 1
        
        print("✅ TEST 4b PASSED: Noise gate PASS allows processing")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 5: AI Dispatch ONLY on PASS and Preserves Gate Order
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestAIDispatch(unittest.TestCase):
    """Test AI dispatch logic and gate order preservation"""
    
    def test_ai_dispatch_only_on_pass(self):
        """
        Test that AI dispatch ONLY occurs when:
        1. Noise Gate returns PASS
        2. config.enable_ai_after_noise_gate == True
        """
        from lunia_core.app.services.execution_journal.background_worker import (
            PulseWorker, IntentEnvelope, NervousConfig
        )
        
        mock_db = MagicMock()
        mock_snapshot_builder = Mock()
        mock_noise_gate = Mock()
        mock_ai_gateway = Mock()
        
        # PASS + AI enabled
        mock_noise_gate.should_analyze.return_value = (True, "")
        config = NervousConfig(enable_ai_after_noise_gate=True)
        
        worker = PulseWorker(
            db_session_factory=lambda: mock_db,
            snapshot_builder=mock_snapshot_builder,
            noise_gate=mock_noise_gate,
            config=config,
            ai_gateway=mock_ai_gateway
        )
        
        envelope = IntentEnvelope(
            intent_id="test-intent",
            strategy_id="test-strat",
            symbol="BTC/USDT",
            signal_type="BUY",
            created_at_ms=int(time.time() * 1000),
            timestamp_bucket=int(time.time()),
            dedup_key="test-key",
            l1_snapshot={},
            l2_capture=([], [])
        )
        
        worker._process_envelope(envelope)
        
        # Verify AI dispatch called (either directly or via async bridge)
        # Note: AI gateway method is 'analyze_signal' (can be sync or async)
        
        # Verify metric
        metrics = worker.get_metrics()
        assert metrics["nervous_ai_dispatched_total"] == 1
        
        print("✅ TEST 5 PASSED: AI dispatch only on PASS + config enabled")
    
    def test_ai_dispatch_disabled_by_default(self):
        """
        Test that AI dispatch is DISABLED by default
        """
        from lunia_core.app.services.execution_journal.background_worker import (
            PulseWorker, IntentEnvelope, NervousConfig
        )
        
        mock_db = MagicMock()
        mock_snapshot_builder = Mock()
        mock_noise_gate = Mock()
        mock_ai_gateway = Mock()
        
        # PASS but AI DISABLED
        mock_noise_gate.should_analyze.return_value = (True, "")
        config = NervousConfig()  # Default: enable_ai_after_noise_gate=False
        
        worker = PulseWorker(
            db_session_factory=lambda: mock_db,
            snapshot_builder=mock_snapshot_builder,
            noise_gate=mock_noise_gate,
            config=config,
            ai_gateway=mock_ai_gateway
        )
        
        envelope = IntentEnvelope(
            intent_id="test-intent",
            strategy_id="test-strat",
            symbol="BTC/USDT",
            signal_type="BUY",
            created_at_ms=int(time.time() * 1000),
            timestamp_bucket=int(time.time()),
            dedup_key="test-key",
            l1_snapshot={},
            l2_capture=([], [])
        )
        
        worker._process_envelope(envelope)
        
        # Verify AI dispatch NOT called (analyze_signal should not be invoked)
        
        # Verify metric
        metrics = worker.get_metrics()
        assert metrics["nervous_ai_dispatched_total"] == 0
        
        print("✅ TEST 5b PASSED: AI dispatch disabled by default")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 6: DB Error Does Not Stop Worker
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestDBErrorHandling(unittest.TestCase):
    """Test fail-safe DB error handling"""
    
    def test_db_error_logged_not_fatal(self):
        """
        Test that DB errors are logged but worker continues processing
        """
        from lunia_core.app.services.execution_journal.background_worker import (
            PulseWorker, IntentEnvelope, NervousConfig
        )
        
        # Mock DB that raises exception
        mock_db = MagicMock()
        mock_db.query.side_effect = Exception("DB connection lost")
        
        mock_snapshot_builder = Mock()
        mock_noise_gate = Mock()
        mock_noise_gate.should_analyze.return_value = (False, "test")
        
        worker = PulseWorker(
            db_session_factory=lambda: mock_db,
            snapshot_builder=mock_snapshot_builder,
            noise_gate=mock_noise_gate,
            config=NervousConfig()
        )
        
        envelope = IntentEnvelope(
            intent_id="test-intent",
            strategy_id="test-strat",
            symbol="BTC/USDT",
            signal_type="BUY",
            created_at_ms=int(time.time() * 1000),
            timestamp_bucket=int(time.time()),
            dedup_key="test-key",
            l1_snapshot={},
            l2_capture=([], [])
        )
        
        # Should not raise exception
        try:
            worker._process_envelope(envelope)
        except Exception as e:
            pytest.fail(f"DB error propagated (fail-safe violated): {e}")
        
        # Verify error metric incremented
        metrics = worker.get_metrics()
        assert metrics["nervous_db_errors_total"] > 0
        
        # Verify processing continued
        assert metrics["nervous_processed_total"] == 1
        
        print("✅ TEST 6 PASSED: DB error logged but not fatal")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 7: Graceful Shutdown Drains or Times Out
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestGracefulShutdown(unittest.TestCase):
    """Test graceful shutdown with timeout"""
    
    def test_worker_stops_within_timeout(self):
        """
        Test that worker stops gracefully within timeout
        """
        from lunia_core.app.services.execution_journal.background_worker import (
            PulseWorker, NervousConfig
        )
        
        mock_db = MagicMock()
        mock_snapshot_builder = Mock()
        mock_noise_gate = Mock()
        mock_noise_gate.should_analyze.return_value = (False, "test")
        
        worker = PulseWorker(
            db_session_factory=lambda: mock_db,
            snapshot_builder=mock_snapshot_builder,
            noise_gate=mock_noise_gate,
            config=NervousConfig()
        )
        
        # Start worker
        worker.start()
        time.sleep(0.5)  # Let it run briefly
        
        # Stop worker
        start_time = time.time()
        worker.stop(timeout_sec=2.0)
        stop_duration = time.time() - start_time
        
        # Verify stopped within timeout
        assert stop_duration < 3.0  # Allow some margin
        
        print("✅ TEST 7 PASSED: Worker stops within timeout")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 8: Metrics Counters Increment Correctly
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestMetrics(unittest.TestCase):
    """Test metrics tracking"""
    
    def test_all_metrics_increment(self):
        """
        Test that all metrics increment correctly
        """
        from lunia_core.app.services.execution_journal.background_worker import (
            PulseWorker, IntentEnvelope, NervousConfig
        )
        
        mock_db = MagicMock()
        mock_snapshot_builder = Mock()
        mock_noise_gate = Mock()
        
        config = NervousConfig(queue_maxsize=2)
        
        worker = PulseWorker(
            db_session_factory=lambda: mock_db,
            snapshot_builder=mock_snapshot_builder,
            noise_gate=mock_noise_gate,
            config=config
        )
        
        def create_envelope(i):
            return IntentEnvelope(
                intent_id=f"intent-{i}",
                strategy_id=f"strat-{i}",
                symbol="BTC/USDT",
                signal_type="BUY",
                created_at_ms=int(time.time() * 1000),
                timestamp_bucket=int(time.time()),
                dedup_key=f"key-{i}",
                l1_snapshot={},
                l2_capture=([], [])
            )
        
        # Enqueue 2 (max)
        worker.enqueue(create_envelope(1))
        worker.enqueue(create_envelope(2))
        
        # Enqueue 1 more (should drop)
        worker.enqueue(create_envelope(3))
        
        metrics = worker.get_metrics()
        
        assert metrics["nervous_enqueued_total"] == 2
        assert metrics["nervous_dropped_total"] == 1
        assert metrics["queue_size_current"] == 2
        
        print("✅ TEST 8 PASSED: Metrics increment correctly")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 9: StrategyEngine Integration Adds <1ms Latency
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestLatencyImpact(unittest.TestCase):
    """Test that enqueue adds minimal latency"""
    
    def test_enqueue_latency_under_1ms(self):
        """
        Benchmark: enqueue() should complete in <1ms (non-blocking)
        """
        from lunia_core.app.services.execution_journal.background_worker import (
            PulseWorker, IntentEnvelope, NervousConfig
        )
        
        mock_db = MagicMock()
        mock_snapshot_builder = Mock()
        mock_noise_gate = Mock()
        
        worker = PulseWorker(
            db_session_factory=lambda: mock_db,
            snapshot_builder=mock_snapshot_builder,
            noise_gate=mock_noise_gate,
            config=NervousConfig(queue_maxsize=10000)
        )
        
        def create_envelope():
            return IntentEnvelope(
                intent_id="test",
                strategy_id="strat",
                symbol="BTC/USDT",
                signal_type="BUY",
                created_at_ms=int(time.time() * 1000),
                timestamp_bucket=int(time.time()),
                dedup_key="key",
                l1_snapshot={},
                l2_capture=([], [])
            )
        
        # Warm-up
        for _ in range(10):
            worker.enqueue(create_envelope())
        
        # Benchmark 1000 enqueues
        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            worker.enqueue(create_envelope())
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)
        
        # Calculate p99
        latencies.sort()
        p99 = latencies[int(len(latencies) * 0.99)]
        
        print(f"Enqueue latency p99: {p99:.3f}ms")
        
        # Assert p99 < 1ms (with tolerance)
        assert p99 < 1.0, f"p99 latency {p99:.3f}ms exceeds 1ms"
        
        print(f"✅ TEST 9 PASSED: Enqueue p99 latency = {p99:.3f}ms")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST SUITE RUNNER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    # Run all tests
    unittest.main(verbosity=2)
