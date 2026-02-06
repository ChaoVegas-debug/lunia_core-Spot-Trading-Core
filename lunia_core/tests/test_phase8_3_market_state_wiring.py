"""
Phase 8.3-Integration: Market State Wiring Tests
Test suite for market enrichment integration into PulseWorker
"""
import time
import unittest
from unittest.mock import Mock, MagicMock

class TestSignalEventModel(unittest.TestCase):
    """Test SignalEvent model has market_state column"""
    
    def test_signal_event_model_has_nullable_market_state(self):
        """Test that SignalEvent has nullable market_state JSONType column"""
        from lunia_core.app.services.execution_journal.models import SignalEvent
        
        # Verify column exists
        assert hasattr(SignalEvent, 'market_state'), "market_state column missing"
        
        # Verify it's nullable
        column = SignalEvent.__table__.columns.get('market_state')
        assert column is not None, "market_state not in __table__.columns"
        assert column.nullable is not False, "market_state should be nullable"
        
        print("✅ TEST  PASSED: SignalEvent has nullable market_state column")


class TestWorkerEnrichment(unittest.TestCase):
    """Test PulseWorker enriches and persists market_state"""
    
    def test_worker_persists_market_state_when_enabled(self):
        """Test that worker computes and persists market_state when enabled"""
        from lunia_core.app.services.execution_journal.background_worker import (
            PulseWorker, NervousConfig, IntentEnvelope
        )
        from lunia_core.app.services.execution_journal.models import SignalEvent
        
        # Mock dependencies
        mock_db = MagicMock()
        mock_session_factory = lambda: mock_db
        mock_snapshot_builder = Mock()
        mock_noise_gate = Mock()
        mock_noise_gate.should_analyze.return_value = (False, "test_block")
        
        # Mock aggregator
        mock_aggregator = Mock()
        sample_market_state = {
            "market_risk_flag": "UNKNOWN",
            "timestamp_ms": int(time.time() * 1000)
        }
        mock_aggregator.aggregate_market_state.return_value = sample_market_state
        
        config = NervousConfig(nervous_enable_market_state=True)
        
        worker = PulseWorker(
            db_session_factory=mock_session_factory,
            snapshot_builder=mock_snapshot_builder,
            noise_gate=mock_noise_gate,
            config=config,
            market_state_aggregator=mock_aggregator
        )
        
        # Mock SignalEvent
        mock_signal_event = Mock(spec=SignalEvent)
        mock_signal_event.id = "test-signal-id"
        mock_signal_event.context_snapshot = None
        mock_db.query.return_value.filter.return_value.first.return_value = mock_signal_event
        
        # Create envelope
        envelope = IntentEnvelope(
            intent_id="test-intent-id",
            strategy_id="test_strategy",
            symbol="BTC/USDT",
            signal_type="BUY",
            created_at_ms=int(time.time() * 1000),
            timestamp_bucket=int(time.time()),
            dedup_key="test:BTC/USDT:BUY:1234",
            l1_snapshot={"price": {"mid": 50000.0, "bid": 49995.0, "ask": 50005.0}},
            l2_capture=([], [])
        )
        
        # Process envelope
        worker._process_envelope(envelope)
        
        # Verify aggregator was called
        assert mock_aggregator.aggregate_market_state.called
        
        # Verify market_state was set
        assert mock_signal_event.market_state == sample_market_state
        
        # Verify metrics
        assert worker.metrics["nervous_market_state_enabled_total"] > 0
        assert worker.metrics["nervous_market_state_built_total"] > 0
        
        print("✅ TEST PASSED: Worker persists market_state when enabled")


class TestFeatureFlag(unittest.TestCase):
    """Test feature flag nervous_enable_market_state"""
    
    def test_disabled_flag_results_in_empty(self):
        """Test that disabled flag results in empty market_state"""
        from lunia_core.app.services.execution_journal.background_worker import (
            PulseWorker, NervousConfig, IntentEnvelope
        )
        
        mock_db = MagicMock()
        mock_session_factory = lambda: mock_db
        mock_snapshot_builder = Mock()
        mock_noise_gate = Mock()
        mock_noise_gate.should_analyze.return_value = (False, "test")
        
        mock_aggregator = Mock()
        
        # Config with market_state DISABLED
        config = NervousConfig(nervous_enable_market_state=False)
        
        worker = PulseWorker(
            db_session_factory=mock_session_factory,
            snapshot_builder=mock_snapshot_builder,
            noise_gate=mock_noise_gate,
            config=config,
            market_state_aggregator=mock_aggregator
        )
        
        mock_signal = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_signal
        
        envelope = IntentEnvelope(
            intent_id="test-id",
            strategy_id="strat",
            symbol="ETH/USDT",
            signal_type="SELL",
            created_at_ms=int(time.time() * 1000),
            timestamp_bucket=int(time.time()),
            dedup_key="test:key",
            l1_snapshot={"price": {"mid": 3000.0, "bid": 2999.0, "ask": 3001.0}},
            l2_capture=([], [])
        )
        
        # Process
        worker._process_envelope(envelope)
        
        # Aggregator should NOT have been called
        assert not mock_aggregator.aggregate_market_state.called
        
        # Metrics should reflect empty
        assert worker.metrics["nervous_market_state_empty_total"] > 0
        assert worker.metrics["nervous_market_state_built_total"] == 0
        
        print("✅ TEST PASSED: Disabled flag results in empty market_state")


class TestAIContext(unittest.TestCase):
    """Test AI context includes market_state and shadow_mode"""
    
    def test_ai_context_contains_market_state(self):
        """Test that _reconstruct_ai_context includes market_state"""
        from lunia_core.app.services.execution_journal.background_worker import (
            PulseWorker, NervousConfig, IntentEnvelope
        )
        from lunia_core.app.services.execution_journal.models import SignalEvent
        
        mock_db = MagicMock()
        mock_session_factory = lambda: mock_db
        mock_snapshot_builder = Mock()
        mock_noise_gate = Mock()
        
        worker = PulseWorker(
            db_session_factory=mock_session_factory,
            snapshot_builder=mock_snapshot_builder,
            noise_gate=mock_noise_gate
        )
        
        # Mock SignalEvent with market_state
        mock_signal = Mock(spec=SignalEvent)
        mock_signal.id = "sig-123"
        mock_signal.context_snapshot = {"l1": {}, "l2": {}}
        mock_signal.market_state = {
            "market_risk_flag": "SAFE"
        }
        
        envelope = IntentEnvelope(
            intent_id="test",
            strategy_id="strat",
            symbol="BTC/USDT",
            signal_type="BUY",
            created_at_ms=123456789,
            timestamp_bucket=123456,
            dedup_key="key",
            l1_snapshot={"price": {"mid": 50000.0}},
            l2_capture=([], [])
        )
        
        # Reconstruct context
        ai_context = worker._reconstruct_ai_context(envelope, mock_signal)
        
        # Verify market_state is present
        assert "market_state" in ai_context
        assert ai_context["market_state"] == mock_signal.market_state
        
        # Verify shadow_mode HARD FLOOR
        assert ai_context["shadow_mode"] is True
        
        print("✅ TEST PASSED: AI context includes market_state and shadow_mode=True")


if __name__ == "__main__":
    unittest.main(verbosity=2)
