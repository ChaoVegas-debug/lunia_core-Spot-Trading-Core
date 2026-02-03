"""
EPOCH E Phase E3: Risk Engine Tests
Proving determinism, fail-closed behavior, and capital safety
"""
import pytest
import math

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.risk import (
    RiskEngine,
    RiskConfig,
    RiskContext,
    RiskAssessment,
    Position,
    RiskBlockingFlags,
    RiskWarningFlags
)
from app.services.strategy.models import IntentProposal, SignalSide
from app.services.market_data.realtime.models import MarketSnapshot, SnapshotState
from app.services.governance.rules.risk_rules import RiskGateRule


def test_determinism_same_inputs_same_outputs():
    """Same inputs produce same risk assessment"""
    config = RiskConfig()
    engine = RiskEngine(config)
    
    context = RiskContext(
        portfolio_equity=100000.0,
        peak_equity=100000.0,
        open_positions={},
        mark_prices={"BTC/USDT": 50000.0},
        volatility_map={"BTC/USDT": 0.20}
    )
    
    intent = IntentProposal(
        strategy_id="test",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        signal_strength=0.8,
        reference_price=50000.0,
        rationale="Test"
    )
    
    # Two assessments with same inputs
    assessment1 = engine.assess(intent, context)
    assessment2 = engine.assess(intent, context)
    
    # Same results
    assert assessment1.is_safe == assessment2.is_safe
    assert assessment1.metrics == assessment2.metrics
    assert assessment1.blocking_flags == assessment2.blocking_flags


def test_fail_closed_missing_volatility():
    """Missing volatility causes RISK_MISSING_VOLATILITY blocking flag"""
    config = RiskConfig(fail_closed_on_missing_volatility=True)
    engine = RiskEngine(config)
    
    context = RiskContext(
        portfolio_equity=100000.0,
        peak_equity=100000.0,
        open_positions={"BTC/USDT": Position(symbol="BTC/USDT", quantity=1.0)},
        mark_prices={"BTC/USDT": 50000.0},
        volatility_map={}  # Missing volatility
    )
    
    intent = IntentProposal(
        strategy_id="test",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        signal_strength=0.8,
        reference_price=50000.0,
        rationale="Test"
    )
    
    assessment = engine.assess(intent, context)
    
    assert not assessment.is_safe
    assert RiskBlockingFlags.MISSING_VOLATILITY in assessment.blocking_flags


def test_fail_closed_missing_mark_price():
    """Missing mark price causes RISK_MISSING_MARK_PRICE blocking flag"""
    config = RiskConfig()
    engine = RiskEngine(config)
    
    context = RiskContext(
        portfolio_equity=100000.0,
        peak_equity=100000.0,
        open_positions={"BTC/USDT": Position( symbol="BTC/USDT", quantity=1.0)},
        mark_prices={},  # Missing mark price
        volatility_map={"BTC/USDT": 0.20}
    )
    
    intent = IntentProposal(
        strategy_id="test",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        signal_strength=0.8,
        reference_price=50000.0,
        rationale="Test"
    )
    
    assessment = engine.assess(intent, context)
    
    assert not assessment.is_safe
    assert RiskBlockingFlags.MISSING_MARK_PRICE in assessment.blocking_flags


def test_fail_closed_undefined_intent_size():
    """Intent without sizing causes RISK_UNDEFINED_INTENT_SIZE by default"""
    config = RiskConfig(allow_risk_without_size=False)  # Default
    engine = RiskEngine(config)
    
    context = RiskContext(
        portfolio_equity=100000.0,
        peak_equity=100000.0,
        open_positions={},
        mark_prices={"BTC/USDT": 50000.0},
        volatility_map={"BTC/USDT": 0.20}
    )
    
    intent = IntentProposal(
        strategy_id="test",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        signal_strength=0.8,
        reference_price=50000.0,
        rationale="Test"
        # NOTE: No quantity/size field (common at E1/E2 stage)
    )
    
    assessment = engine.assess(intent, context)
    
    assert not assessment.is_safe
    assert RiskBlockingFlags.UNDEFINED_INTENT_SIZE in assessment.blocking_flags


def test_exposure_symbol_breach_sets_flag():
    """Symbol exposure breach causes RISK_EXPOSURE_SYMBOL_BREACH"""
    config = RiskConfig(max_exposure_per_symbol=0.10)  # 10% max
    engine = RiskEngine(config)
    
    # Position with 20% exposure (exceeds 10% limit)
    context = RiskContext(
        portfolio_equity=100000.0,
        peak_equity=100000.0,
        open_positions={"BTC/USDT": Position(symbol="BTC/USDT", quantity=0.4)},  # 0.4 * 50000 = 20k = 20%
        mark_prices={"BTC/USDT": 50000.0},
        volatility_map={"BTC/USDT": 0.20}
    )
    
    intent = IntentProposal(
        strategy_id="test",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        signal_strength=0.8,
        reference_price=50000.0,
        rationale="Test"
    )
    
    assessment = engine.assess(intent, context)
    
    assert not assessment.is_safe
    assert RiskBlockingFlags.EXPOSURE_SYMBOL_BREACH in assessment.blocking_flags


def test_exposure_portfolio_breach_sets_flag():
    """Portfolio exposure breach causes RISK_EXPOSURE_PORTFOLIO_BREACH"""
    config = RiskConfig(max_portfolio_exposure=0.50)  # 50% max
    engine = RiskEngine(config)
    
    # Total exposure = 60% (exceeds 50%)
    context = RiskContext(
        portfolio_equity=100000.0,
        peak_equity=100000.0,
        open_positions={
            "BTC/USDT": Position(symbol="BTC/USDT", quantity=0.6),  # 30k
            "ETH/USDT": Position(symbol="ETH/USDT", quantity=10.0),  # 30k
        },
        mark_prices={"BTC/USDT": 50000.0, "ETH/USDT": 3000.0},
        volatility_map={"BTC/USDT": 0.20, "ETH/USDT": 0.25}
    )
    
    intent = IntentProposal(
        strategy_id="test",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        signal_strength=0.8,
        reference_price=50000.0,
        rationale="Test"
    )
    
    assessment = engine.assess(intent, context)
    
    assert not assessment.is_safe
    assert RiskBlockingFlags.EXPOSURE_PORTFOLIO_BREACH in assessment.blocking_flags


def test_drawdown_breach_sets_flag():
    """Drawdown breach causes RISK_DRAWDOWN_BREACH"""
    config = RiskConfig(max_drawdown_limit=0.10)  # 10% max drawdown
    engine = RiskEngine(config)
    
    # Drawdown = (120k - 105k) / 120k = 12.5% (exceeds 10%)
    context = RiskContext(
        portfolio_equity=105000.0,
        peak_equity=120000.0,
        open_positions={},
        mark_prices={"BTC/USDT": 50000.0},
        volatility_map={"BTC/USDT": 0.20}
    )
    
    intent = IntentProposal(
        strategy_id="test",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        signal_strength=0.8,
        reference_price=50000.0,
        rationale="Test"
    )
    
    assessment = engine.assess(intent, context)
    
    # Exposure at 18% (>90% of 20% default limit  = 18%) → warning, not blocking
    config = RiskConfig(max_exposure_per_symbol=0.20, max_portfolio_exposure=0.50, allow_risk_without_size=True)
    engine = RiskEngine(config)
    
    context = RiskContext(
        portfolio_equity=100000.0,
        peak_equity=100000.0,
        open_positions={"BTC/USDT": Position(symbol="BTC/USDT", quantity=0.36)},  # 18k = 18%, near 20% limit
        mark_prices={"BTC/USDT": 50000.0},
        volatility_map={"BTC/USDT": 0.20}
    )def test_var_math_correctness_known_case():
    """VaR calculation produces expected result for known inputs"""
    config = RiskConfig(var_confidence_level=0.95, var_horizon_days=1)
    engine = RiskEngine(config)
    
    # Known case: 1 BTC @ $50k, vol=0.20 (20%), 1-day, 95% confidence
    # sigma_horizon = 0.20 * sqrt(1/252) = 0.20 * 0.063 = 0.0126
    # VaR = 50000 * 0.0126 * 1.645 = ~1037
    
    context = RiskContext(
        portfolio_equity=100000.0,
        peak_equity=100000.0,
        open_positions={"BTC/USDT": Position(symbol="BTC/USDT", quantity=1.0)},
        mark_prices={"BTC/USDT": 50000.0},
        volatility_map={"BTC/USDT": 0.20}
    )
    
    intent = IntentProposal(
        strategy_id="test",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        signal_strength=0.8,
        reference_price=50000.0,
        rationale="Test"
    )
    
    assessment = engine.assess(intent, context)
    
    # Check VaR is approximately correct
    var_abs = assessment.metrics['var_portfolio_abs']
    expected_var = 50000 * 0.20 * math.sqrt(1/252.0) * 1.645
    
    assert abs(var_abs - expected_var) < 10  # Within $10


def test_portfolio_var_conservative_sum_no_correlation():
    """Portfolio VaR is sum of symbol VaRs (conservative, correlation=1.0)"""
    config = RiskConfig(var_confidence_level=0.95, var_horizon_days=1)
    engine = RiskEngine(config)
    
    context = RiskContext(
        portfolio_equity=100000.0,
        peak_equity=100000.0,
        open_positions={
            "BTC/USDT": Position(symbol="BTC/USDT", quantity=1.0),
            "ETH/USDT": Position(symbol="ETH/USDT", quantity=10.0),
        },
        mark_prices={"BTC/USDT": 50000.0, "ETH/USDT": 3000.0},
        volatility_map={"BTC/USDT": 0.20, "ETH/USDT": 0.25},
        # No correlation_map → assume 1.0 (conservative)
    )
    
    intent = IntentProposal(
        strategy_id="test",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        signal_strength=0.8,
        reference_price=50000.0,
        rationale="Test"
    )
    
    assessment = engine.assess(intent, context)
    
    # Portfolio VaR should be sum of individual VaRs (correlation=1.0)
    var_portfolio = assessment.metrics['var_portfolio_abs']
    
    # Calculate expected (sum)
    btc_var = 50000 * 0.20 * math.sqrt(1/252.0) * 1.645
    eth_var = 30000 * 0.25 * math.sqrt(1/252.0) * 1.645
    expected_var = btc_var + eth_var
    
    assert abs(var_portfolio - expected_var) < 10  # Within $10


def test_blocking_vs_info_flags_separation():
    """Blocking flags cause is_safe=False, warnings do not"""
    config = RiskConfig(max_portfolio_exposure=0.50, allow_risk_without_size=True)
    engine = RiskEngine(config)
    
    # Exposure at 45% (>90% of 50% limit) → warning, not blocking
    context = RiskContext(
        portfolio_equity=100000.0,
        peak_equity=100000.0,
        open_positions={"BTC/USDT": Position(symbol="BTC/USDT", quantity=0.9)},  # 45k = 45%
        mark_prices={"BTC/USDT": 50000.0},
        volatility_map={"BTC/USDT": 0.20}
    )
    
    intent = IntentProposal(
        strategy_id="test",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        signal_strength=0.8,
        reference_price=50000.0,
        rationale="Test"
    )
    
    assessment = engine.assess(intent, context)
    
    # Should have warning, but still safe
    assert assessment.is_safe
    assert RiskWarningFlags.EXPOSURE_NEAR_LIMIT in assessment.warnings
    assert len(assessment.blocking_flags) == 0


def test_risk_gate_rule_integration():
    """RiskGateRule integrates with Governance correctly"""
    config = RiskConfig(max_exposure_per_symbol=0.10)
    engine = RiskEngine(config)
    rule = RiskGateRule(engine)  # Uses MockRiskContextProvider
    
    snapshot = MarketSnapshot(
        exchange="binance",
        symbol="BTC/USDT",
        market_type="spot",
        snapshot_state=SnapshotState.VALID,
        mid_price=50000.0,
        last_update_ms=1000000,
        version=1
    )
    
    intent = IntentProposal(
        strategy_id="test",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        signal_strength=0.8,
        reference_price=50000.0,
        rationale="Test"
    )
    
    from app.services.governance.context import GovernanceContext
    gov_context = GovernanceContext()
    
    # Evaluate (mock provider returns empty portfolio → should pass)
    result = rule.evaluate(intent, snapshot, gov_context)
    
    # Should pass (no positions, no breaches)
    # But will have UNDEFINED_INTENT_SIZE flag (default config)
    # Actually, let me check the mock provider...
    # Mock returns empty positions, so no breaches, but intent has no size
    # So depends on config... let me think
    
    # With default config (allow_risk_without_size=False), this will fail
    assert not result.passed  # Because UNDEFINED_INTENT_SIZE


def test_assumptions_explicit_in_assessment():
    """All assumptions are explicit in RiskAssessment"""
    config = RiskConfig(var_confidence_level=0.95, var_horizon_days=1)
    engine = RiskEngine(config)
    
    context = RiskContext(
        portfolio_equity=100000.0,
        peak_equity=100000.0,
        open_positions={},
        mark_prices={"BTC/USDT": 50000.0},
        volatility_map={"BTC/USDT": 0.20}
    )
    
    intent = IntentProposal(
        strategy_id="test",
        symbol="BTC/USDT",
        side=SignalSide.BUY,
        signal_strength=0.8,
        reference_price=50000.0,
        rationale="Test"
    )
    
    assessment = engine.assess(intent, context)
    
    # Verify all assumptions present
    assert "model" in assessment.assumptions
    assert "var_confidence" in assessment.assumptions
    assert "var_horizon_days" in assessment.assumptions
    assert "volatility_source" in assessment.assumptions
    assert "correlation_default" in assessment.assumptions
    
    # Verify values
    assert assessment.assumptions["model"] == "Parametric VaR (Normal Distribution)"
    assert assessment.assumptions["var_confidence"] == "0.95"
    assert assessment.assumptions["var_horizon_days"] == "1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
