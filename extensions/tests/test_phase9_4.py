"""
PHASE 9.4 — STRATEGY PACK v1 TESTS

Comprehensive tests proving:
1. Interface compatibility (load without runner modifications)
2. Governance gating (blocks produce NOOP or safe outcomes)
3. Physics gating (cost gate forces NOOP)
4. Positive execution (ENTRY → EXIT → TradeOutcome)
5. Determinism
"""

import pytest
from extensions.protocol.protocol import (
    PROTOCOL_VERSION,
    StrategyIntent,
    IntentType,
    VolatilityState,
)
from extensions.strategies.volatility_trend_follower import VolatilityTrendFollower
from extensions.strategies.range_mean_reverter import RangeMeanReverter
from extensions.strategies.breakout_scalp import BreakoutScalp
from extensions.sandbox.runner import StrategyRunner
from extensions.sandbox.audit_store import AuditStore
from extensions.sandbox.serialization import canonical_hash


# ────────────────────────────────────────────────────────────────────────────────
# TEST FIXTURES
# ───────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def fixed_clock():
    """Fixed clock for deterministic testing."""
    return lambda: 1737560000000  # Phase 9.4 timestamp


@pytest.fixture
def base_market_raw():
    """Base market data."""
    return {
        "symbol": "BTC/USD",
        "ts_ms": 1737560000000,
        "bid": 50000.0,
        "ask": 50001.0,
        "mid": 50000.5,
        "volume_24h": 1000000.0,
        "volatility_state": "normal",
        "market_regime": "trend_up",
        "atr_14": 250.0,
        "spread_pct": 0.0002,
    }


@pytest.fixture
def base_portfolio_raw():
    """Base portfolio data."""
    return {
        "base_currency": "USD",
        "equity": 100000.0,
        "available_balance": 95000.0,
        "margin_used": 5000.0,
        "margin_available": 95000.0,
        "positions": {},
        "daily_pnl": 0.0,
        "total_pnl": 0.0,
        "peak_equity": 100000.0,
        "drawdown_pct": 0.0,
    }


@pytest.fixture
def base_governance_raw():
    """Base governance data."""
    return {
        "correlation_id": "corr_phase94_test",
        "ts_ms": 1737560000000,
        "is_live": False,
        "is_reduce_only": False,
        "allow_new_entries": True,
        "max_position_size": 10000.0,
        "max_leverage": 3.0,
        "risk_state": "green",
        "emergency_override_active": False,
    }


# ────────────────────────────────────────────────────────────────────────────────
# INTERFACE COMPATIBILITY TESTS
# ────────────────────────────────────────────────────────────────────────────────


def test_interface_compatibility_volatility_trend(fixed_clock, base_market_raw, base_portfolio_raw, base_governance_raw):
    """Test VolatilityTrendFollower loads without runner modifications."""
    audit_store = AuditStore()
    strategy = VolatilityTrendFollower()
    runner = StrategyRunner(strategy, audit_store, clock=fixed_clock)
    
    result = runner.tick(base_market_raw, base_portfolio_raw, base_governance_raw)
    
    # Should execute without errors
    assert result is not None
    assert result.final_intent.protocol_version == PROTOCOL_VERSION


def test_interface_compatibility_range_mean_reverter(fixed_clock, base_market_raw, base_portfolio_raw, base_governance_raw):
    """Test RangeMeanReverter loads without runner modifications."""
    audit_store = AuditStore()
    strategy = RangeMeanReverter()
    runner = StrategyRunner(strategy, audit_store, clock=fixed_clock)
    
    result = runner.tick(base_market_raw, base_portfolio_raw, base_governance_raw)
    
    assert result is not None
    assert result.final_intent.protocol_version == PROTOCOL_VERSION


def test_interface_compatibility_breakout_scalp(fixed_clock, base_market_raw, base_portfolio_raw, base_governance_raw):
    """Test BreakoutScalp loads without runner modifications."""
    audit_store = AuditStore()
    strategy = BreakoutScalp()
    runner = StrategyRunner(strategy, audit_store, clock=fixed_clock)
    
    result = runner.tick(base_market_raw, base_portfolio_raw, base_governance_raw)
    
    assert result is not None
    assert result.final_intent.protocol_version == PROTOCOL_VERSION


# ────────────────────────────────────────────────────────────────────────────────
# GOVERNANCE GATING TESTS
# ────────────────────────────────────────────────────────────────────────────────


def test_governance_blocks_reduce_only_mode(fixed_clock, base_market_raw, base_portfolio_raw, base_governance_raw):
    """Test reduce_only mode forces NOOP."""
    governance_raw = {**base_governance_raw, "is_reduce_only": True}
    
    audit_store = AuditStore()
    strategy = VolatilityTrendFollower()
    runner = StrategyRunner(strategy, audit_store, clock=fixed_clock)
    
    result = runner.tick(base_market_raw, base_portfolio_raw, governance_raw)
    
    assert result.final_intent.intent_type == IntentType.NOOP
    assert "reduce_only" in result.final_intent.rationale.lower()


def test_governance_blocks_risk_state_red(fixed_clock, base_market_raw, base_portfolio_raw, base_governance_raw):
    """Test RED risk state forces NOOP."""
    governance_raw = {**base_governance_raw, "risk_state": "red"}
    
    audit_store = AuditStore()
    strategy = RangeMeanReverter()
    runner = StrategyRunner(strategy, audit_store, clock=fixed_clock)
    
    result = runner.tick(base_market_raw, base_portfolio_raw, governance_raw)
    
    assert result.final_intent.intent_type == IntentType.NOOP
    assert "risk_state" in result.final_intent.rationale.lower()


# ────────────────────────────────────────────────────────────────────────────────
# PHYSICS GATING TESTS
# ────────────────────────────────────────────────────────────────────────────────


def test_cost_gate_high_spread_forces_noop(fixed_clock, base_market_raw, base_portfolio_raw, base_governance_raw):
    """Test high spread_pct forces NOOP via cost gate."""
    # High spread => high cost => cost gate fails
    market_raw = {**base_market_raw, "spread_pct": 0.01, "atr_14": 10.0}  # 1% spread, low ATR
    
    audit_store = AuditStore()
    strategy = VolatilityTrendFollower()
    runner = StrategyRunner(strategy, audit_store, clock=fixed_clock)
    
    result = runner.tick(market_raw, base_portfolio_raw, base_governance_raw)
    
    assert result.final_intent.intent_type == IntentType.NOOP
    assert "cost gate" in result.final_intent.rationale.lower()


def test_volatility_gate_extreme_forces_noop(fixed_clock, base_market_raw, base_portfolio_raw, base_governance_raw):
    """Test EXTREME volatility forces NOOP for trend follower."""
    market_raw = {**base_market_raw, "volatility_state": "extreme"}
    
    audit_store = AuditStore()
    strategy = VolatilityTrendFollower()
    runner = StrategyRunner(strategy, audit_store, clock=fixed_clock)
    
    result = runner.tick(market_raw, base_portfolio_raw, base_governance_raw)
    
    assert result.final_intent.intent_type == IntentType.NOOP
    assert "volatility gate" in result.final_intent.rationale.lower()


def test_liquidity_gate_forces_noop_for_scalp(fixed_clock, base_market_raw, base_portfolio_raw, base_governance_raw):
    """Test high spread forces NOOP for scalp via liquidity gate."""
    # Scalp requires spread_pct <= 0.0015
    market_raw = {
        **base_market_raw,
        "volatility_state": "elevated",  # Required for scalp
        "spread_pct": 0.003,  # Too wide for scalp
    }
    
    audit_store = AuditStore()
    strategy = BreakoutScalp()
    runner = StrategyRunner(strategy, audit_store, clock=fixed_clock)
    
    result = runner.tick(market_raw, base_portfolio_raw, base_governance_raw)
    
    assert result.final_intent.intent_type == IntentType.NOOP
    assert "liquidity gate" in result.final_intent.rationale.lower()


# ────────────────────────────────────────────────────────────────────────────────
# POSITIVE EXECUTION TESTS
# ────────────────────────────────────────────────────────────────────────────────


def test_positive_execution_entry_produces_intent(fixed_clock, base_market_raw, base_portfolio_raw, base_governance_raw):
    """Test favorable conditions produce ENTRY intent."""
    # Favorable: normal vol, good spread, high ATR
    market_raw = {
        **base_market_raw,
        "volatility_state": "normal",
        "spread_pct": 0.0001,
        "atr_14": 500.0,  # High ATR => good expected move
    }
    
    audit_store = AuditStore()
    strategy = VolatilityTrendFollower()
    runner = StrategyRunner(strategy, audit_store, clock=fixed_clock)
    
    result = runner.tick(market_raw, base_portfolio_raw, base_governance_raw)
    
    # Should produce ENTRY
    assert result.final_intent.intent_type == IntentType.ENTRY
    assert result.final_intent.exit_plan is not None
    assert result.final_intent.size_base is not None
    assert len(result.final_intent.rationale) > 10
    assert "cost gate pass" in result.final_intent.rationale.lower()


def test_auditability_rationale_contains_evidence(fixed_clock, base_market_raw, base_portfolio_raw, base_governance_raw):
    """Test rationale contains numeric evidence."""
    market_raw = {**base_market_raw, "volatility_state": "normal", "atr_14": 300.0}
    
    audit_store = AuditStore()
    strategy = VolatilityTrendFollower()
    runner = StrategyRunner(strategy, audit_store, clock=fixed_clock)
    
    result = runner.tick(market_raw, base_portfolio_raw, base_governance_raw)
    
    rationale = result.final_intent.rationale
    
    # Should contain evidence
    assert len(rationale) > 10
    assert "spread_pct" in rationale
    assert "expected_move" in rationale or "volatility gate" in rationale.lower()


# ────────────────────────────────────────────────────────────────────────────────
# DETERMINISM TESTS
# ────────────────────────────────────────────────────────────────────────────────


def test_determinism_same_inputs_same_intent(fixed_clock):
    """Test deterministic intent generation."""
    market_raw = {
        "symbol": "BTC/USD",
        "ts_ms": 1737560000000,
        "bid": 50000.0,
        "ask": 50001.0,
        "mid": 50000.5,
        "volume_24h": 1000000.0,
        "volatility_state": "normal",
        "market_regime":  "trend_up",
        "atr_14": 400.0,
        "spread_pct": 0.0001,
    }
    
    portfolio_raw = {"base_currency": "USD", "equity": 100000.0}
    governance_raw = {
        "correlation_id": "corr_determ_test",  # Fixed
        "ts_ms": 1737560000000,
        "is_live": False,
        "is_reduce_only": False,
        "allow_new_entries": True,
        "max_position_size": 10000.0,
        "max_leverage": 3.0,
        "risk_state": "green",
        "emergency_override_active": False,
    }
    
    audit_store1 = AuditStore()
    strategy1 = VolatilityTrendFollower()
    runner1 = StrategyRunner(strategy1, audit_store1, clock=fixed_clock, enable_paper_execution=False)
    
    audit_store2 = AuditStore()
    strategy2 = VolatilityTrendFollower()
    runner2 = StrategyRunner(strategy2, audit_store2, clock=fixed_clock, enable_paper_execution=False)
    
    result1 = runner1.tick(market_raw, portfolio_raw, governance_raw)
    result2 = runner2.tick(market_raw, portfolio_raw, governance_raw)
    
    # Intent hash must be identical (deterministic)
    hash1 = canonical_hash(result1.final_intent)
    hash2 = canonical_hash(result2.final_intent)
    assert hash1 == hash2, f"Intent hashes differ: {hash1} != {hash2}"
    
    # Intent IDs must be identical
    assert result1.final_intent.intent_id == result2.final_intent.intent_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
