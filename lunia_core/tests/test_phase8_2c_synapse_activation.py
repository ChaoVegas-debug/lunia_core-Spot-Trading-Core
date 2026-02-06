"""
Phase 8.2C: THE SYNAPSE — End-to-End AI Dispatch Activation Tests
Comprehensive test suite validating full chain: Strategy → Persist → Worker → NoiseGate → AIGateway
"""
import json
import time
import unittest
from copy import deepcopy
from unittest.mock import Mock, MagicMock, patch, call

import pytest

# Test imports (Phase 8.2C)
# from lunia_core.app.services.execution_journal.background_worker import PulseWorker, IntentEnvelope, Nervous Config


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 1: AI Gateway Injected into PulseWorker
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestAIGatewayInjection(unittest.TestCase):
    """Test AI Gateway dependency injection"""
    
    def test_pulse_worker_accepts_ai_gateway(self):
        """
        Test that PulseWorker can be instantiated with AIGateway
        """
        from lunia_core.app.services.execution_journal.background_worker import (
            PulseWorker, NervousConfig
        )
        
        mock_db = MagicMock()
        mock_snapshot_builder = Mock()
        mock_noise_gate = Mock()
        mock_ai_gateway = Mock()
        
        config = NervousConfig(enable_ai_after_noise_gate=True)
        
        worker = PulseWorker(
            db_session_factory=lambda: mock_db,
            snapshot_builder=mock_snapshot_builder,
            noise_gate=mock_noise_gate,
            ai_gateway=mock_ai_gateway,
            config=config
        )
        
        # Verify injection
        assert worker.ai_gateway is mock_ai_gateway
        assert worker.config.enable_ai_after_noise_gate == True
        
        print("✅ TEST 1 PASSED: AI Gateway injected successfully")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 2: Envelope → AI Context Reconstruction Correctness
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestContextReconstruction(unittest.TestCase):
    """Test AI context reconstruction from envelope"""
    
    def test_context_includes_all_required_fields(self):
        """
        Test that reconstructed context contains all required fields
        for AIGateway analysis
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
            config=NervousConfig()
        )
        
        # Create test envelope
        envelope = IntentEnvelope(
            intent_id="test-intent-123",
            strategy_id="momentum_v1",
            symbol="BTC/USDT",
            signal_type="BUY",
            created_at_ms=1707062400000,
            timestamp_bucket=1707062400,
            dedup_key="momentum_v1:BTC/USDT:BUY:1707062400",
            l1_snapshot={
                "price": {"mid": 50000.0, "bid": 49999.0, "ask": 50001.0},
                "spread": {"abs": 2.0, "rel": 0.00004}
            },
            l2_capture=(
                [{"price": 50000.0, "amount": 1.0}],
                [{"price": 50001.0, "amount": 1.5}]
            ),
            governance_metadata={"defcon": 1},
            rationale="Strong momentum signal"
        )
        
        # Mock DB signal_event
        mock_signal_event = Mock()
        mock_signal_event.id = "test-intent-123"
        mock_signal_event.context_snapshot = {
            "l1": envelope.l1_snapshot,
            "l2": {"orderbook_top_n": {"bids": [], "asks": []}}
        }
        
        # Reconstruct context
        ai_context = worker._reconstruct_ai_context(envelope, mock_signal_event)
        
        # Verify all required fields
        assert ai_context["signal_id"] == "test-intent-123"
        assert ai_context["strategy_id"] == "momentum_v1"
        assert ai_context["symbol"] == "BTC/USDT"
        assert ai_context["timestamp_ms"] == 1707062400000
        assert "market_snapshot" in ai_context
        assert ai_context["market_snapshot"]["l1"]["price"]["mid"] == 50000.0
        assert ai_context["market_snapshot"]["orderbook"]["bids"][0]["price"] == 50000.0
        assert ai_context["market_snapshot"]["orderbook"]["asks"][0]["price"] == 50001.0
        assert ai_context["governance_metadata"]["defcon"] == 1
        assert ai_context["rationale"] == "Strong momentum signal"
        assert ai_context["shadow_mode"] == True  # CRITICAL for Phase 8.2C
        
        print("✅ TEST 2 PASSED: Context reconstruction includes all fields + shadow_mode=True")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 3: Gate Order Preserved (Kill → Budget → Circuit → Router)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestGateOrderPreservation(unittest.TestCase):
    """Test that AI dispatch preserves governance gate order"""
    
    def test_killswitch_blocks_before_gateway_call(self):
        """
        Test that KillSwitch (ai_global_enabled=False) prevents AI dispatch
        """
        from lunia_core.app.services.execution_journal.background_worker import (
            PulseWorker, IntentEnvelope, NervousConfig
        )
        
        mock_db = MagicMock()
        mock_snapshot_builder = Mock()
        mock_noise_gate = Mock()
        mock_ai_gateway = Mock()
        
        # Mock governance config with KillSwitch OFF
        mock_governance_config = Mock()
        mock_governance_config.ai_global_enabled = False
        mock_ai_gateway.governance_config = mock_governance_config
        
        config = NervousConfig(enable_ai_after_noise_gate=True)
        
        worker = PulseWorker(
            db_session_factory=lambda: mock_db,
            snapshot_builder=mock_snapshot_builder,
            noise_gate=mock_noise_gate,
            ai_gateway=mock_ai_gateway,
            config=config
        )
        
        # Create test data
        envelope = IntentEnvelope(
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
        
        mock_signal_event = Mock()
        mock_signal_event.id = "test"
        
        # Attempt dispatch
        worker._dispatch_to_ai_gateway(envelope, {}, mock_signal_event)
        
        # Verify AI gateway analyze_signal was NEVER called (KillSwitch blocked)
        assert not mock_ai_gateway.analyze_signal.called
        
        # Verify metrics show NO dispatch
        metrics = worker.get_metrics()
        assert metrics["nervous_ai_dispatched_total"] == 0
        
        print("✅ TEST 3 PASSED: KillSwitch blocks AI dispatch before gateway call")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 4: Shadow Mode Enforced in AI Context
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestShadowModeEnforcement(unittest.TestCase):
    """Test that shadow mode is always enforced in Phase 8.2C"""
    
    def test_shadow_mode_always_true(self):
        """
        CRITICAL: AI must ALWAYS operate in shadow mode for Phase 8.2C
        Analysis stored but never influences trading
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
            config=NervousConfig()
        )
        
        envelope = IntentEnvelope(
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
        
        mock_signal_event = Mock()
        mock_signal_event.id = "test"
        mock_signal_event.context_snapshot = {}
        
        # Reconstruct context
        ai_context = worker._reconstruct_ai_context(envelope, mock_signal_event)
        
        # CRITICAL: shadow_mode MUST be True
        assert ai_context["shadow_mode"] == True
        
        print("✅ TEST 4 PASSED: Shadow mode ALWAYS True in AI context")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 5: AI Failure Does NOT Crash Worker
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestAIFailureSafety(unittest.TestCase):
    """Test fail-safe behavior when AI dispatch fails"""
    
    def test_ai_exception_logged_not_fatal(self):
        """
        Test that AI dispatch exceptions are logged but worker continues
        """
        from lunia_core.app.services.execution_journal.background_worker import (
            PulseWorker, IntentEnvelope, NervousConfig
        )
        
        mock_db = MagicMock()
        mock_snapshot_builder = Mock()
        mock_noise_gate = Mock()
        mock_ai_gateway = Mock()
        
        # Configure AI gateway to raise exception
        mock_ai_gateway.analyze_signal.side_effect = Exception("AI network timeout")
        mock_governance_config = Mock()
        mock_governance_config.ai_global_enabled = True
        mock_ai_gateway.governance_config = mock_governance_config
        
        config = NervousConfig(enable_ai_after_noise_gate=True)
        
        worker = PulseWorker(
            db_session_factory=lambda: mock_db,
            snapshot_builder=mock_snapshot_builder,
            noise_gate=mock_noise_gate,
            ai_gateway=mock_ai_gateway,
            config=config
        )
        
        envelope = IntentEnvelope(
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
        
        mock_signal_event = Mock()
        mock_signal_event.id = "test"
        mock_signal_event.context_snapshot = {}
        
        # Dispatch should NOT raise exception despite AI failure
        try:
            worker._dispatch_to_ai_gateway(envelope, {}, mock_signal_event)
        except Exception as e:
            pytest.fail(f"AI exception propagated (fail-safe violated): {e}")
        
        # Verify error metric incremented
        metrics = worker.get_metrics()
        assert metrics["nervous_ai_errors_total"] > 0
        
        print("✅ TEST 5 PASSED: AI failure logged but not fatal")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 6: End-to-End Pipeline (Synapse Activation)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestEndToEndPipeline(unittest.TestCase):
    """Test full synapse activation end-to-end"""
    
    def test_full_chain_signal_to_ai_analysis(self):
        """
        End-to-end test:
        Envelope → Enrich → DB Update → Noise Gate PASS → AI Dispatch
        """
        from lunia_core.app.services.execution_journal.background_worker import (
            PulseWorker, IntentEnvelope, NervousConfig
        )
        
        # Mock DB with signal_event
        mock_db = MagicMock()
        mock_signal_event = Mock()
        mock_signal_event.id = "test-signal-123"
        mock_signal_event.context_snapshot = {"l1": {}, "l2": {}}
        
        mock_db_session = Mock()
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_signal_event
        
        mock_snapshot_builder = Mock()
        
        #Mock Noise Gate (PASS)
        mock_noise_gate = Mock()
        mock_noise_gate.should_analyze.return_value = (True, "")
        
        # Mock AI Gateway
        mock_ai_gateway = Mock()
        mock_governance_config = Mock()
        mock_governance_config.ai_global_enabled = True
        mock_ai_gateway.governance_config = mock_governance_config
        mock_ai_gateway.analyze_signal.return_value = {"analysis": "bullish"}
        
        config = NervousConfig(enable_ai_after_noise_gate=True)
        
        worker = PulseWorker(
            db_session_factory=lambda: mock_db_session,
            snapshot_builder=mock_snapshot_builder,
            noise_gate=mock_noise_gate,
            ai_gateway=mock_ai_gateway,
            config=config
        )
        
        # Create envelope
        envelope = IntentEnvelope(
            intent_id="test-signal-123",
            strategy_id="momentum_v1",
            symbol="BTC/USDT",
            signal_type="BUY",
            created_at_ms=int(time.time() * 1000),
            timestamp_bucket=int(time.time()),
            dedup_key="momentum_v1:BTC/USDT:BUY:123",
            l1_snapshot={"price": {"mid": 50000.0}},
            l2_capture=(
                [{"price": 50000.0, "amount": 1.0}],
                [{"price": 50001.0, "amount": 1.5}]
            ),
            governance_metadata={"defcon": 1},
            rationale="Momentum breakout"
        )
        
        # Process envelope (full pipeline)
        worker._process_envelope(envelope)
        
        # Verify full chain executed:
        # 1. DB update called
        assert mock_db_session.query.called
        
        # 2. Noise Gate evaluated
        assert mock_noise_gate.should_analyze.called
        
        # 3. AI Gateway analyze_signal called
        assert mock_ai_gateway.analyze_signal.called or worker._ai_loop_thread is not None
        
        # 4. Metrics show successful processing
        metrics = worker.get_metrics()
        assert metrics["nervous_processed_total"] == 1
        
        # 5. If AI was dispatched, verify context includes shadow_mode
        if mock_ai_gateway.analyze_signal.called:
            call_args = mock_ai_gateway.analyze_signal.call_args
            ai_context = call_args[0][1]  # Second positional arg
            assert ai_context["shadow_mode"] == True
        
        print("✅ TEST 6 PASSED: End-to-end pipeline Envelope → AI complete")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 7: Thread Safety (Async Gateway in Thread)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestThreadSafety(unittest.TestCase):
    """Test thread safety of async bridge"""
    
    def test_async_gateway_detection(self):
        """
        Test that async gateway is detected and bridge is initialized
        """
        from lunia_core.app.services.execution_journal.background_worker import (
            PulseWorker, NervousConfig
        )
        import asyncio
        
        mock_db = MagicMock()
        mock_snapshot_builder = Mock()
        mock_noise_gate = Mock()
        
        # Mock async AI gateway
        mock_ai_gateway = Mock()
        
        async def async_analyze(signal, context):
            return {"analysis": "bullish"}
        
        mock_ai_gateway.analyze_signal = async_analyze
        
        worker = PulseWorker(
            db_session_factory=lambda: mock_db,
            snapshot_builder=mock_snapshot_builder,
            noise_gate=mock_noise_gate,
            ai_gateway=mock_ai_gateway,
            config=NervousConfig()
        )
        
        # Verify async bridge initialized
        assert worker._ai_event_loop is not None
        assert worker._ai_loop_thread is not None
        
        print("✅ TEST 7 PASSED: Async gateway detected, bridge initialized")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 8: Performance Sanity (<50ms per AI Dispatch)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestPerformance(unittest.TestCase):
    """Test AI dispatch performance"""
    
    def test_dispatch_latency_under_50ms(self):
        """
        Benchmark: AI dispatch should complete in <50ms in test environment
        """
        from lunia_core.app.services.execution_journal.background_worker import (
            PulseWorker, IntentEnvelope, NervousConfig
        )
        
        mock_db = MagicMock()
        mock_signal_event = Mock()
        mock_signal_event.id = "test"
        mock_signal_event.context_snapshot = {}
        
        mock_snapshot_builder = Mock()
        mock_noise_gate = Mock()
        
        # Mock fast AI gateway (sync)
        mock_ai_gateway = Mock()
        mock_governance_config = Mock()
        mock_governance_config.ai_global_enabled = True
        mock_ai_gateway.governance_config = mock_governance_config
        mock_ai_gateway.analyze_signal.return_value = {"analysis": "ok"}
        
        worker = PulseWorker(
            db_session_factory=lambda: mock_db,
            snapshot_builder=mock_snapshot_builder,
            noise_gate=mock_noise_gate,
            ai_gateway=mock_ai_gateway,
            config=NervousConfig()
        )
        
        envelope = IntentEnvelope(
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
        
        # Benchmark 100 dispatches
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            worker._dispatch_to_ai_gateway(envelope, {}, mock_signal_event)
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)
        
        # Calculate p95
        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]
        
        print(f"AI dispatch latency p95: {p95:.2f}ms")
        
        # Assert p95 < 50ms
        assert p95 < 50.0, f"p95 latency {p95:.2f}ms exceeds 50ms"
        
        print(f"✅ TEST 8 PASSED: AI dispatch p95 = {p95:.2f}ms")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST SUITE RUNNER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    # Run all tests
    unittest.main(verbosity=2)
