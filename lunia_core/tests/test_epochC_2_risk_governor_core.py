"""
Test Epoch C.2 — Risk Governor Core Logic

Tests for PositionExposureGovernor hard/soft limits, fail-closed behavior,
shadow mode, and determinism.
"""
import pytest

from lunia_core.app.services.council.models import CouncilVerdict
from lunia_core.app.services.execution_bridge.models import OrderPlan
from lunia_core.app.services.risk_governor.config import RiskLimits
from lunia_core.app.services.risk_governor.governor import PositionExposureGovernor
from lunia_core.app.services.risk_governor.models import (
    Decision,
    PendingOrderExposure,
    PortfolioSnapshot,
    Position,
    ReasonCode,
)
from lunia_core.app.services.risk_governor.window_store import (
    CircuitBreakerState,
    WindowCounterStore,
)


def make_verdict(decision="APPROVE") -> CouncilVerdict:
    """Helper: Create test verdict"""
    return CouncilVerdict(
        id="test-verdict-123",
        proposal_id="test-proposal-123",
        decision=decision,
        reasoning="Test verdict rationale",
    )


def make_plan(symbol="BTCUSDT", side="BUY", quantity=0.1) -> OrderPlan:
    """Helper: Create test order plan"""
    return OrderPlan(
        id="test-plan-123",
        verdict_id="test-verdict-123",
        symbol=symbol,
        side=side,
        quantity=quantity,
        sizing_logic="Test sizing logic",
    )


def make_snapshot(
    equity=100000.0,
    positions=None,
    prices=None,
    pending=None,
    as_of_ms=1000000,
) -> PortfolioSnapshot:
    """Helper: Create test portfolio snapshot"""
    return PortfolioSnapshot(
        as_of_ms=as_of_ms,
        total_equity=equity,
        positions=positions or [],
        prices=prices or {"BTCUSDT": 50000.0, "ETHUSDT": 3000.0},
        pending=pending or [],
    )


# =============================================================================
# HARD LIMIT TESTS (BLOCK)
# =============================================================================

def test_missing_snapshot_blocks():
    """Missing portfolio snapshot → BLOCK (fail-closed)"""
    governor = PositionExposureGovernor(
        window_store=WindowCounterStore(),
        circuit_breaker=CircuitBreakerState(),
    )
    
    verdict = make_verdict()
    plan = make_plan()
    limits = RiskLimits()
    
    decision = governor.evaluate(
        verdict=verdict,
        plan=plan,
        snapshot=None,  # Missing!
        adapter_name="binance",
        now_ms=1000000,
        limits=limits,
    )
    
    assert decision.decision == Decision.BLOCK
    assert ReasonCode.MISSING_PORTFOLIO_SNAPSHOT in decision.reason_codes


def test_missing_price_blocks():
    """Missing price for symbol → BLOCK (fail-closed)"""
    governor = PositionExposureGovernor(
        window_store=WindowCounterStore(),
        circuit_breaker=CircuitBreakerState(),
    )
    
    verdict = make_verdict()
    plan = make_plan(symbol="SOLUSDT")
    snapshot = make_snapshot(prices={"BTCUSDT": 50000.0})  # SOL missing!
    limits = RiskLimits()
    
    decision = governor.evaluate(
        verdict=verdict,
        plan=plan,
        snapshot=snapshot,
        adapter_name="binance",
        now_ms=1000000,
        limits=limits,
    )
    
    assert decision.decision == Decision.BLOCK
    assert ReasonCode.MISSING_PRICE in decision.reason_codes


def test_stale_snapshot_blocks():
    """Stale snapshot (> max_age) → BLOCK"""
    governor = PositionExposureGovernor(
        window_store=WindowCounterStore(),
        circuit_breaker=CircuitBreakerState(),
    )
    
    verdict = make_verdict()
    plan = make_plan()
    snapshot = make_snapshot(as_of_ms=1000000)  # Snapshot from 1000000
    limits = RiskLimits(snapshot_max_age_ms=5000)
    
    decision = governor.evaluate(
        verdict=verdict,
        plan=plan,
        snapshot=snapshot,
        adapter_name="binance",
        now_ms=1020000,  # Now at 1020000 → age 20000ms > 5000ms
        limits=limits,
    )
    
    assert decision.decision == Decision.BLOCK
    assert ReasonCode.DATA_STALE in decision.reason_codes


def test_order_notional_cap_blocks():
    """Order notional > max → BLOCK"""
    governor = PositionExposureGovernor(
        window_store=WindowCounterStore(),
        circuit_breaker=CircuitBreakerState(),
    )
    
    verdict = make_verdict()
    plan = make_plan(quantity=0.1)  # 0.1 BTC @ 50000 = $5000
    snapshot = make_snapshot(equity=100000.0)  # 2% cap = $2000
    limits = RiskLimits(max_order_notional_pct_of_equity=0.02)
    
    decision = governor.evaluate(
        verdict=verdict,
        plan=plan,
        snapshot=snapshot,
        adapter_name="binance",
        now_ms=1000000,
        limits=limits,
    )
    
    assert decision.decision == Decision.BLOCK
    assert ReasonCode.ORDER_NOTIONAL_TOO_LARGE in decision.reason_codes


def test_symbol_position_cap_blocks():
    """Projected symbol position > max → BLOCK"""
    governor = PositionExposureGovernor(
        window_store=WindowCounterStore(),
        circuit_breaker=CircuitBreakerState(),
    )
    
    verdict = make_verdict()
    plan = make_plan(quantity=0.15)  # +0.15 BTC = +$7500
    
    # Existing position: 0.1 BTC @ 50000 = $5000
    snapshot = make_snapshot(
        equity=100000.0,
        positions=[
            Position(
                symbol="BTCUSDT",
                side="LONG",
                quantity=0.1,
                avg_entry_price=50000.0,
                mark_price=50000.0,
                notional=5000.0,
            )
        ],
    )
    
    # Projected: 5000 + 7500 = 12500 > 10000 (10% cap)
    limits = RiskLimits(max_position_notional_pct_of_equity=0.10)
    
    decision = governor.evaluate(
        verdict=verdict,
        plan=plan,
        snapshot=snapshot,
        adapter_name="binance",
        now_ms=1000000,
        limits=limits,
    )
    
    assert decision.decision == Decision.BLOCK
    assert ReasonCode.SYMBOL_POSITION_CAP_EXCEEDED in decision.reason_codes


def test_gross_exposure_cap_blocks():
    """Projected gross exposure > max → BLOCK"""
    governor = PositionExposureGovernor(
        window_store=WindowCounterStore(),
        circuit_breaker=CircuitBreakerState(),
    )
    
    verdict = make_verdict()
    plan = make_plan(quantity=0.5)  # 0.5 BTC = $25000
    
    # Existing: BTC LONG $20000, ETH LONG $15000 → gross $35000
    snapshot = make_snapshot(
        equity=100000.0,
        positions=[
            Position(
                symbol="BTCUSDT",
                side="LONG",
                quantity=0.4,
                avg_entry_price=50000.0,
                mark_price=50000.0,
                notional=20000.0,
            ),
            Position(
                symbol="ETHUSDT",
                side="LONG",
                quantity=5.0,
                avg_entry_price=3000.0,
                mark_price=3000.0,
                notional=15000.0,
            ),
        ],
    )
    
    # Projected: 35000 + 25000 = 60000 > 50000 (50% cap)
    limits = RiskLimits(max_total_gross_exposure_pct_of_equity=0.50)
    
    decision = governor.evaluate(
        verdict=verdict,
        plan=plan,
        snapshot=snapshot,
        adapter_name="binance",
        now_ms=1000000,
        limits=limits,
    )
    
    assert decision.decision == Decision.BLOCK
    assert ReasonCode.GROSS_EXPOSURE_CAP_EXCEEDED in decision.reason_codes


def test_net_exposure_cap_blocks():
    """Projected net exposure > max → BLOCK"""
    governor = PositionExposureGovernor(
        window_store=WindowCounterStore(),
        circuit_breaker=CircuitBreakerState(),
    )
    
    verdict = make_verdict()
    plan = make_plan(quantity=0.6)  # BUY 0.6 BTC = +$30000
    
    # Current net: LONG $10000 - SHORT $5000 = +$5000
    snapshot = make_snapshot(
        equity=100000.0,
        positions=[
            Position(
                symbol="BTCUSDT",
                side="LONG",
                quantity=0.2,
                avg_entry_price=50000.0,
                mark_price=50000.0,
                notional=10000.0,
            ),
            Position(
                symbol="ETHUSDT",
                side="SHORT",
                quantity=1.67,
                avg_entry_price=3000.0,
                mark_price=3000.0,
                notional=-5000.0,
            ),
        ],
    )
    
    # Projected net: 5000 + 30000 = 35000 > 25000 (25% cap)
    limits = RiskLimits(max_total_net_exposure_pct_of_equity=0.25)
    
    decision = governor.evaluate(
        verdict=verdict,
        plan=plan,
        snapshot=snapshot,
        adapter_name="binance",
        now_ms=1000000,
        limits=limits,
    )
    
    assert decision.decision == Decision.BLOCK
    assert ReasonCode.NET_EXPOSURE_CAP_EXCEEDED in decision.reason_codes


def test_cluster_exposure_cap_blocks():
    """Projected cluster exposure > max → BLOCK"""
    governor = PositionExposureGovernor(
        window_store=WindowCounterStore(),
        circuit_breaker=CircuitBreakerState(),
    )
    
    verdict = make_verdict()
    plan = make_plan(symbol="ETHUSDT", quantity=5.0)  # 5 ETH = $15000
    
    snapshot = make_snapshot(
        equity=100000.0,
        positions=[
            Position(
                symbol="BTCUSDT",
                side="LONG",
                quantity=0.3,
                avg_entry_price=50000.0,
                mark_price=50000.0,
                notional=15000.0,
            ),
        ],
    )
    
    # Both BTC and ETH in "CRYPTO_L1" cluster
    # Projected cluster: 15000 + 15000 = 30000 > 25000 (25% cap)
    limits = RiskLimits(
        max_cluster_gross_exposure_pct_of_equity=0.25,
        correlation_clusters={"BTCUSDT": "CRYPTO_L1", "ETHUSDT": "CRYPTO_L1"},
    )
    
    decision = governor.evaluate(
        verdict=verdict,
        plan=plan,
        snapshot=snapshot,
        adapter_name="binance",
        now_ms=1000000,
        limits=limits,
    )
    
    assert decision.decision == Decision.BLOCK
    assert ReasonCode.CLUSTER_EXPOSURE_CAP_EXCEEDED in decision.reason_codes


# =============================================================================
# SOFT LIMIT TESTS (WARN)
# =============================================================================

def test_soft_warn_triggers_manual_review():
    """Soft limit violation → MANUAL_REVIEW (default)"""
    governor = PositionExposureGovernor(
        window_store=WindowCounterStore(),
        circuit_breaker=CircuitBreakerState(),
    )
    
    verdict = make_verdict()
    plan = make_plan(quantity=0.04)  # 0.04 BTC @ 50000 = $2000
    snapshot = make_snapshot(equity=100000.0)
    
    # Hard limit: 2% ($2000) ✅
    # Soft limit: 1.5% ($1500) ❌
    limits = RiskLimits(
        max_order_notional_pct_of_equity=0.02,
        warn_order_notional_pct_of_equity=0.015,
        soft_action="MANUAL_REVIEW",
    )
    
    decision = governor.evaluate(
        verdict=verdict,
        plan=plan,
        snapshot=snapshot,
        adapter_name="binance",
        now_ms=1000000,
        limits=limits,
    )
    
    assert decision.decision == Decision.REQUIRES_MANUAL_REVIEW
    assert ReasonCode.SOFT_WARN_SYMBOL_CONCENTRATION in decision.reason_codes


def test_soft_warn_downgrade_mode():
    """Soft limit violation → DOWNGRADE (when configured)"""
    governor = PositionExposureGovernor(
        window_store=WindowCounterStore(),
        circuit_breaker=CircuitBreakerState(),
    )
    
    verdict = make_verdict()
    plan = make_plan(quantity=0.04)  # $2000
    snapshot = make_snapshot(equity=100000.0)
    
    limits = RiskLimits(
        max_order_notional_pct_of_equity=0.02,
        warn_order_notional_pct_of_equity=0.015,
        soft_action="DOWNGRADE_TO_DRY_RUN",
    )
    
    decision = governor.evaluate(
        verdict=verdict,
        plan=plan,
        snapshot=snapshot,
        adapter_name="binance",
        now_ms=1000000,
        limits=limits,
    )
    
    assert decision.decision == Decision.DOWNGRADE_TO_DRY_RUN


# =============================================================================
# SPECIAL MODES
# =============================================================================

def test_shadow_mode_logs_only_allows():
    """Shadow mode → LOG_ONLY (always allow)"""
    governor = PositionExposureGovernor(
        window_store=WindowCounterStore(),
        circuit_breaker=CircuitBreakerState(),
    )
    
    verdict = make_verdict()
    plan = make_plan(quantity=0.1)
    snapshot = make_snapshot(equity=100000.0)
    
    limits = RiskLimits(shadow_mode=True)
    
    decision = governor.evaluate(
        verdict=verdict,
        plan=plan,
        snapshot=snapshot,
        adapter_name="binance",
        now_ms=1000000,
        limits=limits,
    )
    
    assert decision.decision == Decision.LOG_ONLY


def test_fail_closed_on_exception():
    """Internal error → BLOCK (fail-closed)"""
    governor = PositionExposureGovernor(
        window_store=WindowCounterStore(),
        circuit_breaker=CircuitBreakerState(),
    )
    
    verdict = make_verdict()
    plan = make_plan()
    
    # Malformed snapshot will cause internal error
    snapshot = PortfolioSnapshot(
        as_of_ms=1000000,
        total_equity=100000.0,
        positions=[],
        prices={},  # Missing price!
        pending=[],
    )
    
    limits = RiskLimits()
    
    decision = governor.evaluate(
        verdict=verdict,
        plan=plan,
        snapshot=snapshot,
        adapter_name="binance",
        now_ms=1000000,
        limits=limits,
    )
    
    # Should fail-closed
    assert decision.decision == Decision.BLOCK
    # Could be MISSING_PRICE or INTERNAL_ERROR_FAIL_CLOSED


# =============================================================================
# DETERMINISM & ACCOUNTING TESTS
# =============================================================================

def test_determinism_same_inputs_same_decision():
    """Same inputs → same decision (deterministic)"""
    governor = PositionExposureGovernor(
        window_store=WindowCounterStore(),
        circuit_breaker=CircuitBreakerState(),
    )
    
    verdict = make_verdict()
    plan = make_plan()
    snapshot = make_snapshot()
    limits = RiskLimits()
    
    # Run twice with identical inputs
    decision1 = governor.evaluate(
        verdict=verdict,
        plan=plan,
        snapshot=snapshot,
        adapter_name="binance",
        now_ms=1000000,
        limits=limits,
    )
    
    decision2 = governor.evaluate(
        verdict=verdict,
        plan=plan,
        snapshot=snapshot,
        adapter_name="binance",
        now_ms=1000000,
        limits=limits,
    )
    
    # Decisions should be identical (except IDs and window count)
    assert decision1.decision == decision2.decision
    assert decision1.reason_codes == decision2.reason_codes


def test_pessimistic_pending_included():
    """Pending orders included in exposure calculations (pessimistic)"""
    governor = PositionExposureGovernor(
        window_store=WindowCounterStore(),
        circuit_breaker=CircuitBreakerState(),
    )
    
    verdict = make_verdict()
    plan = make_plan(quantity=0.03)  # $1500 (below hard cap of $2000)
    
    # Pending orders: $20000
    snapshot = make_snapshot(
        equity=100000.0,
        positions=[],
        pending=[
            PendingOrderExposure(
                symbol="BTCUSDT",
                cluster_id="UNCLUSTERED",
                notional=20000.0,
                created_at_ms=999000,
            ),
        ],
    )
    
    # Projected gross: 0 + 20000 (pending) + 1500 (new) = 21500
    # 50% hard cap = 50000 → PASS
    # 20% soft cap = 20000 → WARN (21500 > 20000)
    limits = RiskLimits(
        max_order_notional_pct_of_equity=0.10,  # Raise to 10% ($10k) to avoid hitting order cap
        max_position_notional_pct_of_equity=0.25,  # Raise to 25% to accommodate pending+new (21500)
        max_total_gross_exposure_pct_of_equity=0.50,
        warn_total_gross_exposure_pct_of_equity=0.20,  # Lower threshold
    )
    
    decision = governor.evaluate(
        verdict=verdict,
        plan=plan,
        snapshot=snapshot,
        adapter_name="binance",
        now_ms=1000000,
        limits=limits,
    )
    
    # Should warn (21500 > 20000)
    assert decision.decision == Decision.REQUIRES_MANUAL_REVIEW
    assert ReasonCode.SOFT_WARN_GROSS_EXPOSURE in decision.reason_codes
