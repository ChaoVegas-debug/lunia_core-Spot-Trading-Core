"""
PHASE 9.2 — COMPREHENSIVE TESTS

Tests proving:
- Canonical serialization determinism
- Audit store integrity hash stability
- Validator rejects invalid intents
- Runner survives crashing strategy
- Runner creates audit trail
- No frozen dataclass mutations

SPEC IMPROVEMENT: All tests use injectable clock for determinism.
"""

import pytest
import time
from extensions.protocol.protocol import (
    PROTOCOL_VERSION,
    StrategyIntent,
    TradeExitPlan,
    IntentType,
    TradeDirection,
    StrategyFrequency,
    GovernanceContext,
    MarketSnapshot,
    ShadowPortfolio,
    VolatilityState,
    MarketRegime,
    RiskState,
)
from extensions.sandbox.serialization import (
    to_canonical_json,
    canonical_hash,
    verify_determinism,
    CanonicalSerializationError,
)
from extensions.sandbox.audit_store import AuditStore, create_audit_event
from extensions.sandbox.context_factory import ContextFactory, ContextFactoryError
from extensions.sandbox.validator import ValidationChain, ValidationResult
from extensions.sandbox.runner import StrategyRunner, TickResult
from extensions.sandbox.reject_codes import RejectCode
from extensions.strategies.reference_noop import ReferenceNoopStrategy


# ────────────────────────────────────────────────────────────────────────────────
# TEST FIXTURES
# ────────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def fixed_clock():
    """Fixed clock for deterministic testing."""
    return lambda: 1737543014000  # Fixed timestamp


@pytest.fixture
def sample_governance_raw():
    """Sample raw governance data."""
    return {
        "correlation_id": "corr_test_123",
        "run_id": "run_test_456",
        "ts_ms": 1737543014000,
        "is_live": False,
        "is_reduce_only": False,
        "allow_new_entries": True,
        "max_position_size": 10000.0,
        "max_leverage": 3.0,
        "risk_state": "green",
        "emergency_override_active": False,
    }


@pytest.fixture
def sample_market_raw():
    """Sample raw market data."""
    return {
        "symbol": "BTC/USD",
        "ts_ms": 1737543014000,
        "bid": 50000.12345678,
        "ask": 50001.87654321,
        "mid": 50001.0,
        "volume_24h": 1234567.89,
        "volatility_state": "normal",
        "market_regime": "trend_up",
        "atr_14": 500.0,
        "spread_pct": 0.003,
    }


@pytest.fixture
def sample_portfolio_raw():
    """Sample raw portfolio data."""
    return {
        "base_currency": "USD",
        "equity": 100000.0,
        "available_balance": 95000.0,
        "margin_used": 5000.0,
        "margin_available": 95000.0,
        "positions": {},
        "daily_pnl": 1000.0,
        "total_pnl": 5000.0,
        "peak_equity": 105000.0,
        "drawdown_pct": 4.76,
    }


# ────────────────────────────────────────────────────────────────────────────────
# SERIALIZATION TESTS
# ────────────────────────────────────────────────────────────────────────────────


def test_canonical_serialization_determinism():
    """Test that canonical serialization is deterministic."""
    exit_plan = TradeExitPlan(
        stop_loss_pct=2.0,
        take_profit_pct=5.0,
        stop_loss_price=None,
        take_profit_price=None,
        time_limit_ms=None,
        trail_start_pct=None,
    )
    
    intent = StrategyIntent(
        intent_id="a1b2c3d4e5f67890",
        ts_ms=1737543014000,
        protocol_version=PROTOCOL_VERSION,
        correlation_id="corr_test_123",
        intent_type=IntentType.ENTRY,
        direction=TradeDirection.LONG,
        symbol="BTC/USD",
        size_base=0.5,
        size_quote=None,
        exit_plan=exit_plan,
        confidence=0.85,
        rationale="Test intent",
        strategy_id="test_strategy",
        strategy_frequency=StrategyFrequency.INTRADAY,
    )
    
    # Verify determinism
    assert verify_determinism(intent, iterations=10)
    
    # Verify hash stability
    hash1 = canonical_hash(intent)
    hash2 = canonical_hash(intent)
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA256 hex


def test_canonical_serialization_forbids_nan():
    """Test that NaN values are rejected."""
    data = {"value": float('nan')}
    with pytest.raises(CanonicalSerializationError, match="NaN"):
        to_canonical_json(data)


def test_canonical_serialization_forbids_infinity():
    """Test that Infinity values are rejected."""
    data = {"value": float('inf')}
    with pytest.raises(CanonicalSerializationError, match="Infinity"):
        to_canonical_json(data)


def test_float_precision_applied():
    """Test that float precision is applied consistently."""
    data = {"price": 50000.123456789}
    json_str = to_canonical_json(data)
    # Should be rounded to 8 decimals
    assert "50000.12345679" in json_str


# ────────────────────────────────────────────────────────────────────────────────
# AUDIT STORE TESTS
# ────────────────────────────────────────────────────────────────────────────────


def test_audit_store_integrity_hash_stable():
    """Test that audit store integrity hash is stable."""
    store = AuditStore()
    
    # Add events
    event1 = create_audit_event(
        ts_ms=1737543014000,
        event_type="test_event_1",
        correlation_id="corr_123",
        run_id="run_456",
        payload={"data": "value1"},
    )
    event2 = create_audit_event(
        ts_ms=1737543014001,
        event_type="test_event_2",
        correlation_id="corr_123",
        run_id="run_456",
        payload={"data": "value2"},
    )
    
    store.append(event1)
    store.append(event2)
    
    # Get integrity hash multiple times
    hash1 = store.integrity_hash()
    hash2 = store.integrity_hash()
    
    assert hash1 == hash2
    assert len(hash1) == 64


def test_audit_event_immutable():
    """Test that AuditEvent is frozen (SPEC IMPROVEMENT)."""
    event = create_audit_event(
        ts_ms=1737543014000,
        event_type="test",
        correlation_id="corr_123",
        run_id="run_456",
        payload={},
    )
    
    # Attempt to modify should fail
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        event.ts_ms = 999


# ────────────────────────────────────────────────────────────────────────────────
# CONTEXT FACTORY TESTS
# ────────────────────────────────────────────────────────────────────────────────


def test_context_factory_creates_governance(fixed_clock, sample_governance_raw):
    """Test context factory creates valid governance context."""
    factory = ContextFactory(clock=fixed_clock)
    gov = factory.create_governance_context(sample_governance_raw)
    
    assert gov.correlation_id == "corr_test_123"
    assert gov.run_id == "run_test_456"
    assert gov.ts_ms == 1737543014000
    assert gov.risk_state == RiskState.GREEN


def test_context_factory_rejects_unknown_enum(fixed_clock):
    """Test context factory rejects unknown enum values (SPEC IMPROVEMENT)."""
    factory = ContextFactory(clock=fixed_clock)
    
    raw = {
        "risk_state": "unknown_state",
        "is_live": False,
        "max_position_size": 10000.0,
        "max_leverage": 3.0,
    }
    
    with pytest.raises(ContextFactoryError) as exc_info:
        factory.create_governance_context(raw)
    
    assert exc_info.value.reject_code == RejectCode.CONTEXT_FACTORY_ENUM_UNKNOWN


def test_context_factory_rejects_missing_field(fixed_clock):
    """Test context factory rejects missing required fields."""
    factory = ContextFactory(clock=fixed_clock)
    
    raw = {
        "risk_state": "green",
        # Missing is_live
    }
    
    with pytest.raises(ContextFactoryError) as exc_info:
        factory.create_governance_context(raw)
    
    assert exc_info.value.reject_code in [
        RejectCode.CONTEXT_FACTORY_MISSING_FIELD,
        RejectCode.CONTEXT_FACTORY_TYPE_ERROR,
    ]


# ────────────────────────────────────────────────────────────────────────────────
# VALIDATOR TESTS
# ────────────────────────────────────────────────────────────────────────────────


def test_validator_rejects_wrong_protocol_version(sample_governance_raw, fixed_clock):
    """Test validator rejects protocol version mismatch."""
    factory = ContextFactory(clock=fixed_clock)
    gov = factory.create_governance_context(sample_governance_raw)
    
    # Create intent with wrong version (SPEC IMPROVEMENT: no mutation)
    intent = StrategyIntent(
        intent_id="a1b2c3d4e5f67890",
        ts_ms=gov.ts_ms,
        protocol_version="0.0.0",  # Wrong version
        correlation_id=gov.correlation_id,
        intent_type=IntentType.NOOP,
        direction=None,
        symbol=None,
        size_base=None,
        size_quote=None,
        exit_plan=None,
        confidence=1.0,
        rationale="Test",
        strategy_id="test",
        strategy_frequency=StrategyFrequency.POSITION,
    )
    
    validator = ValidationChain()
    result = validator.validate(intent, gov)
    
    assert not result.is_valid
    assert result.reject_code == RejectCode.PROTOCOL_VERSION_MISMATCH


def test_validator_rejects_entry_missing_exit_plan(sample_governance_raw, fixed_clock):
    """Test validator rejects ENTRY without exit_plan."""
    factory = ContextFactory(clock=fixed_clock)
    gov = factory.create_governance_context(sample_governance_raw)
    
    intent = StrategyIntent(
        intent_id="a1b2c3d4e5f67890",
        ts_ms=gov.ts_ms,
        protocol_version=PROTOCOL_VERSION,
        correlation_id=gov.correlation_id,
        intent_type=IntentType.ENTRY,
        direction=TradeDirection.LONG,
        symbol="BTC/USD",
        size_base=0.5,
        size_quote=None,
        exit_plan=None,  # Missing!
        confidence=0.8,
        rationale="Test",
        strategy_id="test",
        strategy_frequency=StrategyFrequency.INTRADAY,
    )
    
    validator = ValidationChain()
    result = validator.validate(intent, gov)
    
    assert not result.is_valid
    assert result.reject_code == RejectCode.ENTRY_MISSING_EXIT_PLAN


def test_validator_rejects_empty_exit_plan(sample_governance_raw, fixed_clock):
    """Test validator rejects exit plan with no conditions."""
    factory = ContextFactory(clock=fixed_clock)
    gov = factory.create_governance_context(sample_governance_raw)
    
    # Exit plan with all None values
    exit_plan = TradeExitPlan(
        stop_loss_price=None,
        stop_loss_pct=None,
        take_profit_price=None,
        take_profit_pct=None,
        time_limit_ms=None,
        trail_start_pct=None,
    )
    
    intent = StrategyIntent(
        intent_id="a1b2c3d4e5f67890",
        ts_ms=gov.ts_ms,
        protocol_version=PROTOCOL_VERSION,
        correlation_id=gov.correlation_id,
        intent_type=IntentType.ENTRY,
        direction=TradeDirection.LONG,
        symbol="BTC/USD",
        size_base=0.5,
        size_quote=None,
        exit_plan=exit_plan,
        confidence=0.8,
        rationale="Test",
        strategy_id="test",
        strategy_frequency=StrategyFrequency.INTRADAY,
    )
    
    validator = ValidationChain()
    result = validator.validate(intent, gov)
    
    assert not result.is_valid
    assert result.reject_code == RejectCode.EXIT_PLAN_EMPTY


def test_validator_rejects_governance_blocks(fixed_clock):
    """Test validator respects governance blocks."""
    factory = ContextFactory(clock=fixed_clock)
    
    # Risk state BLACK
    gov_raw = {
        "correlation_id": "corr_123",
        "run_id": "run_456",
        "ts_ms": 1737543014000,
        "is_live": False,
        "is_reduce_only": False,
        "allow_new_entries": True,
        "max_position_size": 10000.0,
        "max_leverage": 3.0,
        "risk_state": "black",  # BLACK state
        "emergency_override_active": False,
    }
    
    gov = factory.create_governance_context(gov_raw)
    
    intent = StrategyIntent(
        intent_id="a1b2c3d4e5f67890",
        ts_ms=gov.ts_ms,
        protocol_version=PROTOCOL_VERSION,
        correlation_id=gov.correlation_id,
        intent_type=IntentType.ENTRY,
        direction=TradeDirection.LONG,
        symbol="BTC/USD",
        size_base=0.5,
        size_quote=None,
        exit_plan=TradeExitPlan(
            stop_loss_pct=2.0,
            take_profit_pct=None,
            stop_loss_price=None,
            take_profit_price=None,
            time_limit_ms=None,
            trail_start_pct=None,
        ),
        confidence=0.8,
        rationale="Test",
        strategy_id="test",
        strategy_frequency=StrategyFrequency.INTRADAY,
    )
    
    validator = ValidationChain()
    result = validator.validate(intent, gov)
    
    assert not result.is_valid
    assert result.reject_code == RejectCode.GOVERNANCE_RISK_STATE_BLACK


def test_validator_rejects_invalid_confidence(sample_governance_raw, fixed_clock):
    """Test validator rejects out-of-range confidence."""
    factory = ContextFactory(clock=fixed_clock)
    gov = factory.create_governance_context(sample_governance_raw)
    
    intent = StrategyIntent(
        intent_id="a1b2c3d4e5f67890",
        ts_ms=gov.ts_ms,
        protocol_version=PROTOCOL_VERSION,
        correlation_id=gov.correlation_id,
        intent_type=IntentType.NOOP,
        direction=None,
        symbol=None,
        size_base=None,
        size_quote=None,
        exit_plan=None,
        confidence=1.5,  # Out of range
        rationale="Test",
        strategy_id="test",
        strategy_frequency=StrategyFrequency.POSITION,
    )
    
    validator = ValidationChain()
    result = validator.validate(intent, gov)
    
    assert not result.is_valid
    assert result.reject_code == RejectCode.CONFIDENCE_OUT_OF_RANGE


# ────────────────────────────────────────────────────────────────────────────────
# RUNNER TESTS
# ────────────────────────────────────────────────────────────────────────────────


def test_runner_survives_crashing_strategy(sample_market_raw, sample_portfolio_raw, sample_governance_raw, fixed_clock):
    """Test runner contains strategy exceptions and creates audit trail."""
    
    class CrashingStrategy:
        """Strategy that always crashes."""
        def generate_intent(self, governance, portfolio, markets):
            raise RuntimeError("Intentional crash for testing")
    
    audit_store = AuditStore()
    strategy = CrashingStrategy()
    runner = StrategyRunner(strategy, audit_store, clock=fixed_clock)
    
    result = runner.tick(sample_market_raw, sample_portfolio_raw, sample_governance_raw)
    
    # Runner should not crash
    assert result is not None
    assert result.strategy_error is not None
    assert "RuntimeError" in result.strategy_error
    
    # Should produce safe NOOP
    assert result.final_intent.intent_type == IntentType.NOOP
    assert "crashed" in result.final_intent.rationale.lower()
    
    # Should have audit trail
    assert len(result.audit_event_ids) > 0
    
    # Check audit events
    events = audit_store.get_events_by_correlation_id(result.correlation_id)
    event_types = [e.event_type for e in events]
    assert "strategy_crashed" in event_types


def test_runner_creates_audit_trail_for_normal_tick(sample_market_raw, sample_portfolio_raw, sample_governance_raw, fixed_clock):
    """Test runner creates complete audit trail for successful tick."""
    audit_store = AuditStore()
    strategy = ReferenceNoopStrategy()
    runner = StrategyRunner(strategy, audit_store, clock=fixed_clock)
    
    result = runner.tick(sample_market_raw, sample_portfolio_raw, sample_governance_raw)
    
    # Should succeed
    assert result.strategy_error is None
    assert result.final_intent.intent_type == IntentType.NOOP
    
    # Should have audit trail
    events = audit_store.get_events_by_correlation_id(result.correlation_id)
    event_types = [e.event_type for e in events]
    
    # Should have: tick_start, intent_generated, intent_validated, tick_end
    assert "tick_start" in event_types
    assert "intent_generated" in event_types
    assert "intent_validated" in event_types
    assert "tick_end" in event_types


def test_runner_replaces_rejected_intent_with_noop(sample_market_raw, sample_portfolio_raw, sample_governance_raw, fixed_clock):
    """Test runner replaces rejected intent with safe NOOP."""
    
    class InvalidIntentStrategy:
        """Strategy that returns invalid intent (wrong protocol version)."""
        def generate_intent(self, governance, portfolio, markets):
            return StrategyIntent(
                intent_id="a1b2c3d4e5f67890",
                ts_ms=governance.ts_ms,
                protocol_version="0.0.0",  # Wrong!
                correlation_id=governance.correlation_id,
                intent_type=IntentType.NOOP,
                direction=None,
                symbol=None,
                size_base=None,
                size_quote=None,
                exit_plan=None,
                confidence=1.0,
                rationale="Test",
                strategy_id="invalid_strategy",
                strategy_frequency=StrategyFrequency.POSITION,
            )
    
    audit_store = AuditStore()
    strategy = InvalidIntentStrategy()
    runner = StrategyRunner(strategy, audit_store, clock=fixed_clock)
    
    result = runner.tick(sample_market_raw, sample_portfolio_raw, sample_governance_raw)
    
    # Should be replaced
    assert result.was_replaced
    assert not result.validation_result.is_valid
    assert result.validation_result.reject_code == RejectCode.PROTOCOL_VERSION_MISMATCH
    
    # Final intent should be safe NOOP
    assert result.final_intent.intent_type == IntentType.NOOP
    assert result.final_intent.protocol_version == PROTOCOL_VERSION
    
    # Should have replacement event in audit
    events = audit_store.get_events_by_correlation_id(result.correlation_id)
    event_types = [e.event_type for e in events]
    assert "intent_replaced_with_noop" in event_types


# ────────────────────────────────────────────────────────────────────────────────
# INTEGRATION TESTS
# ────────────────────────────────────────────────────────────────────────────────


def test_full_pipeline_determinism(sample_market_raw, sample_portfolio_raw, sample_governance_raw, fixed_clock):
    """Test that full pipeline is deterministic with fixed clock."""
    audit_store1 = AuditStore()
    strategy1 = ReferenceNoopStrategy()
    runner1 = StrategyRunner(strategy1, audit_store1, clock=fixed_clock)
    
    audit_store2 = AuditStore()
    strategy2 = ReferenceNoopStrategy()
    runner2 = StrategyRunner(strategy2, audit_store2, clock=fixed_clock)
    
    result1 = runner1.tick(sample_market_raw, sample_portfolio_raw, sample_governance_raw)
    result2 = runner2.tick(sample_market_raw, sample_portfolio_raw, sample_governance_raw)
    
    # Results should be identical
    assert result1.final_intent.intent_id == result2.final_intent.intent_id
    assert canonical_hash(result1.final_intent) == canonical_hash(result2.final_intent)
    
    # Audit stores should have same integrity hash
    assert audit_store1.integrity_hash() == audit_store2.integrity_hash()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
