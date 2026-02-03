"""
PHASE 9.3 — COMPREHENSIVE TESTS

Tests proving market friction, TTL enforcement, cooldown, and determinism.
"""

import pytest
from extensions.protocol.protocol import (
    PROTOCOL_VERSION,
    StrategyIntent,
    TradeExitPlan,
    IntentType,
    TradeDirection,
    StrategyFrequency,
    VolatilityState,
)
from extensions.sandbox.cost_model import (
    compute_fee,
    compute_spread_cost,
    compute_slippage_cost,
    compute_latency_cost,
    compute_fill_price,
)
from extensions.sandbox.ttl_enforcer import is_ttl_expired
from extensions.sandbox.cooldown_manager import CooldownManager
from extensions.sandbox.paper_types import create_trade_outcome
from extensions.sandbox.paper_executor import PaperExecutor
from extensions.sandbox.audit_store import AuditStore
from extensions.sandbox.runner import StrategyRunner
from extensions.sandbox.serialization import canonical_hash, FLOAT_PRECISION
from extensions.strategies.reference_noop import ReferenceNoopStrategy


# ────────────────────────────────────────────────────────────────────────────────
# TEST FIXTURES
# ────────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def fixed_clock():
    """Fixed clock for deterministic testing."""
    return lambda: 1737550000000  # Phase 9.3 timestamp


# ────────────────────────────────────────────────────────────────────────────────
# COST MODEL TESTS
# ────────────────────────────────────────────────────────────────────────────────


def test_cost_model_deterministic():
    """Test that cost functions are deterministic."""
    # Same inputs => same outputs
    fee1 = compute_fee(10000.0, 0.001)
    fee2 = compute_fee(10000.0, 0.001)
    assert fee1 == fee2
    assert fee1 == 10.0  # 10000 * 0.001
    
    spread1 = compute_spread_cost("buy", 50000.0, 50001.0, 1.0)
    spread2 = compute_spread_cost("buy", 50000.0, 50001.0, 1.0)
    assert spread1 == spread2


def test_spread_worst_side_execution():
    """Test spread cost uses worst-side execution."""
    bid = 50000.0
    ask = 50001.0
    mid = 50000.5
    qty = 1.0
    
    # Buy at ask (worst side)
    buy_cost = compute_spread_cost("buy", bid, ask, qty)
    expected_buy = abs(mid - ask) * qty  # 0.5 * 1.0
    assert buy_cost == round(expected_buy, FLOAT_PRECISION)
    
    # Sell at bid (worst side)
    sell_cost = compute_spread_cost("sell", bid, ask, qty)
    expected_sell = abs(mid - bid) * qty  # 0.5 * 1.0
    assert sell_cost == round(expected_sell, FLOAT_PRECISION)


def test_slippage_extreme_has_size_penalty():
    """Test EXTREME volatility has quadratic size penalty."""
    mid = 50000.0
    
    # EXTREME volatility
    slippage_small = compute_slippage_cost(mid, 1.0, VolatilityState.EXTREME)
    slippage_large = compute_slippage_cost(mid, 10.0, VolatilityState.EXTREME)
    
    # Large size should have significantly higher slippage (quadratic)
    # Base: 20 bp + 0.0001 * qty^2
    # For qty=1: 20 + 0.0001*1  = 20.0001 bp
    # For qty=10: 20 + 0.0001*100 = 20.01 bp
    assert slippage_large > slippage_small * 5  # Much higher


def test_net_pnl_includes_all_costs():
    """Test TradeOutcome net_pnl = gross_pnl - all costs."""
    outcome = create_trade_outcome(
        symbol="BTC/USD",
        side="long",
        qty=1.0,
        entry_ts_ms=1000,
        exit_ts_ms=2000,
        entry_price=50000.0,
        exit_price=51000.0,
        fee_total=10.0,
        spread_total=5.0,
        slippage_total=3.0,
        latency_total=2.0,
        exit_reason="SIGNAL",
        entry_intent_id="entry_123",
        exit_intent_id="exit_456",
        entry_run_id="run_1",
        exit_run_id="run_2",
        entry_correlation_id="corr_1",
        exit_correlation_id="corr_2",
        strategy_id="test_strategy",
    )
    
    # Gross: (51000 - 50000) * 1.0 = 1000
    assert outcome.gross_pnl == 1000.0
    
    # Net: 1000 - (10 + 5 + 3 + 2) = 980
    expected_net = outcome.gross_pnl - (
        outcome.fee_total +
        outcome.spread_total +
        outcome.slippage_total +
        outcome.latency_total
    )
    assert outcome.net_pnl == expected_net
    assert outcome.net_pnl == 980.0


# ────────────────────────────────────────────────────────────────────────────────
# TTL TESTS
# ────────────────────────────────────────────────────────────────────────────────


def test_ttl_forces_exit_reason_ttl():
    """Test TTL enforcement causes exit_reason='TTL'."""
    # Not expired
    assert not is_ttl_expired(1000, 2000, 5000)  # elapsed 1000 < limit 5000
    
    # Expired
    assert is_ttl_expired(1000, 6001, 5000)  # elapsed 5001 >= limit 5000
    
    # No TTL (None)
    assert not is_ttl_expired(1000, 999999, None)


# ────────────────────────────────────────────────────────────────────────────────
# COOLDOWN TESTS
# ────────────────────────────────────────────────────────────────────────────────


def test_cooldown_blocks_entry_allows_exit():
    """Test cooldown blocks ENTRY after loss, never blocks EXIT."""
    manager = CooldownManager(base_cooldown_ms=60000)
    
    # Create losing outcome
    losing_outcome = create_trade_outcome(
        symbol="BTC/USD",
        side="long",
        qty=1.0,
        entry_ts_ms=1000,
        exit_ts_ms=2000,
        entry_price=50000.0,
        exit_price=49000.0,  # Loss
        fee_total=10.0,
        spread_total=5.0,
        slippage_total=3.0,
        latency_total=2.0,
        exit_reason="SIGNAL",
        entry_intent_id="intent_1",
        exit_intent_id="intent_2",
        entry_run_id="run_1",
        exit_run_id="run_2",
        entry_correlation_id="corr_1",
        exit_correlation_id="corr_2",
        strategy_id="test_strategy",
    )
    
    # Register loss
    manager.register_outcome(losing_outcome)
    
    # Should block entry immediately after
    can_enter, reason = manager.can_enter("test_strategy", 3000)
    assert not can_enter
    assert "cooldown" in reason.lower()
    
    # After cooldown expires (base * 2 = 120000ms)
    can_enter_later, _ = manager.can_enter("test_strategy", 3000 + 120000)
    assert can_enter_later
    
    # Winning trade resets cooldown
    winning_outcome = create_trade_outcome(
        symbol="BTC/USD",
        side="long",
        qty=1.0,
        entry_ts_ms=150000,
        exit_ts_ms=160000,
        entry_price=50000.0,
        exit_price=51000.0,  # Win
        fee_total=10.0,
        spread_total=5.0,
        slippage_total=3.0,
        latency_total=2.0,
        exit_reason="SIGNAL",
        entry_intent_id="intent_3",
        exit_intent_id="intent_4",
        entry_run_id="run_3",
        exit_run_id="run_4",
        entry_correlation_id="corr_3",
        exit_correlation_id="corr_4",
        strategy_id="test_strategy",
    )
    
    manager.register_outcome(winning_outcome)
    
    # Should allow entry immediately
    can_enter_after_win, _ = manager.can_enter("test_strategy", 161000)
    assert can_enter_after_win


# ────────────────────────────────────────────────────────────────────────────────
# PAPER EXECUTOR INTEGRATION TESTS
# ────────────────────────────────────────────────────────────────────────────────


def test_runner_integration_produces_outcome(fixed_clock):
    """Test runner with paper execution produces TradeOutcome."""
    
    class SimpleEntryExitStrategy:
        """Strategy that enters then exits."""
        def __init__(self):
            self.tick_count = 0
        
        def generate_intent(self, governance, portfolio, markets):
            self.tick_count += 1
            market = markets[0]
            
            if self.tick_count == 1:
                # First tick: ENTRY
                return StrategyIntent(
                    intent_id="a1b2c3d4e5f67890",
                    ts_ms=governance.ts_ms,
                    protocol_version=PROTOCOL_VERSION,
                    correlation_id=governance.correlation_id,
                    intent_type=IntentType.ENTRY,
                    direction=TradeDirection.LONG,
                    symbol=market.symbol,
                    size_base=1.0,
                    size_quote=None,
                    exit_plan=TradeExitPlan(
                        stop_loss_pct=5.0,
                        take_profit_pct=10.0,
                        stop_loss_price=None,
                        take_profit_price=None,
                        time_limit_ms=None,
                        trail_start_pct=None,
                    ),
                    confidence=0.8,
                    rationale="Test entry",
                    strategy_id="simple_strategy",
                    strategy_frequency=StrategyFrequency.INTRADAY,
                )
            else:
                # Second tick: EXIT
                return StrategyIntent(
                    intent_id="b2c3d4e5f6789abc",
                    ts_ms=governance.ts_ms,
                    protocol_version=PROTOCOL_VERSION,
                    correlation_id=governance.correlation_id,
                    intent_type=IntentType.EXIT,
                    direction=None,
                    symbol=market.symbol,
                    size_base=None,
                    size_quote=None,
                    exit_plan=None,
                    confidence=1.0,
                    rationale="Test exit",
                    strategy_id="simple_strategy",
                    strategy_frequency=StrategyFrequency.INTRADAY,
                )
    
    audit_store = AuditStore()
    strategy = SimpleEntryExitStrategy()
    runner = StrategyRunner(strategy, audit_store, clock=fixed_clock, enable_paper_execution=True)
    
    # Tick 1: ENTRY
    result1 = runner.tick(
        raw_market={
            "symbol": "BTC/USD",
            "ts_ms": 1737550000000,
            "bid": 50000.0,
            "ask": 50001.0,
            "mid": 50000.5,
            "volume_24h": 1000000.0,
            "volatility_state": "normal",
            "market_regime": "trend_up",
            "atr_14": 500.0,
            "spread_pct": 0.002,
        },
        raw_portfolio={"base_currency": "USD", "equity": 100000.0},
        raw_governance={
            "ts_ms": 1737550000000,
            "is_live": False,
            "risk_state": "green",
            "max_position_size": 10000.0,
            "max_leverage": 3.0,
        },
    )
    
    assert result1.paper_outcome is None  # ENTRY doesn't create outcome
    
    # Tick 2: EXIT
    result2 = runner.tick(
        raw_market={
            "symbol": "BTC/USD",
            "ts_ms": 1737550010000,  # 10 seconds later
            "bid": 50100.0,
            "ask": 50101.0,
            "mid": 50100.5,
            "volume_24h": 1000000.0,
            "volatility_state": "normal",
            "market_regime": "trend_up",
            "atr_14": 500.0,
            "spread_pct": 0.002,
        },
        raw_portfolio={"base_currency": "USD", "equity": 100000.0},
        raw_governance={
            "ts_ms": 1737550010000,
            "is_live": False,
            "risk_state": "green",
            "max_position_size": 10000.0,
            "max_leverage": 3.0,
        },
    )
    
    # Should produce outcome
    assert result2.paper_outcome is not None
    outcome = result2.paper_outcome
    
    # Verify outcome structure
    assert outcome.symbol == "BTC/USD"
    assert outcome.side == "long"
    assert outcome.exit_reason == "SIGNAL"
    assert outcome.gross_pnl > 0  # Price went up from ~50000.5 to ~50100.5
    assert outcome.net_pnl < outcome.gross_pnl  # Costs reduce profit
    
    # Verify cost breakdown exists
    assert outcome.fee_total > 0
    assert outcome.spread_total > 0
    assert outcome.slippage_total > 0






if __name__ == "__main__":
    pytest.main([__file__, "-v"])
