"""
Test Epoch C.2 — Cluster Correlation Rules

Tests for correlation clustering and cluster-level exposure limits.
"""
import pytest

from lunia_core.app.services.council.models import CouncilVerdict
from lunia_core.app.services.execution_bridge.models import OrderPlan
from lunia_core.app.services.risk_governor.config import RiskLimits
from lunia_core.app.services.risk_governor.governor import PositionExposureGovernor
from lunia_core.app.services.risk_governor.models import (
    Decision,
    PortfolioSnapshot,
    Position,
    ReasonCode,
)
from lunia_core.app.services.risk_governor.window_store import (
    CircuitBreakerState,
    WindowCounterStore,
)


def make_verdict() -> CouncilVerdict:
    """Helper: Create test verdict"""
    return CouncilVerdict(
        id="test-verdict-123",
        proposal_id="test-proposal-123",
        decision="APPROVE",
        reasoning="Test verdict rationale",
    )


def make_plan(symbol="BTCUSDT", quantity=0.1) -> OrderPlan:
    """Helper: Create test plan"""
    return OrderPlan(
        id="test-plan-123",
        verdict_id="test-verdict-123",
        symbol=symbol,
        side="BUY",
        quantity=quantity,
        sizing_logic="Test sizing logic",
    )


def make_snapshot(equity=100000.0, positions=None) -> PortfolioSnapshot:
    """Helper: Create snapshot"""
    return PortfolioSnapshot(
        as_of_ms=1000000,
        total_equity=equity,
        positions=positions or [],
        prices={
            "BTCUSDT": 50000.0,
            "ETHUSDT": 3000.0,
            "SOLUSDT": 100.0,
            "ADAUSDT": 0.5,
        },
        pending=[],
    )


def test_cluster_mapping_applies():
    """Cluster mapping groups correlated symbols"""
    governor = PositionExposureGovernor(
        window_store=WindowCounterStore(),
        circuit_breaker=CircuitBreakerState(),
    )
    
    verdict = make_verdict()
    plan = make_plan(symbol="ETHUSDT", quantity=5.0)  # 5 ETH @ 3000 = $15000
    
    # Existing BTC position: $20000
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
        ],
    )
    
    # Both in "CRYPTO_L1" cluster
    # Cluster exposure: 20000 + 15000 = 35000 > 30000 (30% cap)
    limits = RiskLimits(
        max_cluster_gross_exposure_pct_of_equity=0.30,
        correlation_clusters={
            "BTCUSDT": "CRYPTO_L1",
            "ETHUSDT": "CRYPTO_L1",
        },
    )
    
    decision = governor.evaluate(
        verdict=verdict,
        plan=plan,
        snapshot=snapshot,
        adapter_name="binance",
        now_ms=1000500,
        limits=limits,
    )
    
    assert decision.decision == Decision.BLOCK
    assert ReasonCode.CLUSTER_EXPOSURE_CAP_EXCEEDED in decision.reason_codes
    assert decision.correlation_cluster_id == "CRYPTO_L1"


def test_unclustered_default():
    """Symbols without explicit cluster use default"""
    governor = PositionExposureGovernor(
        window_store=WindowCounterStore(),
        circuit_breaker=CircuitBreakerState(),
    )
    
    verdict = make_verdict()
    plan = make_plan(symbol="SOLUSDT", quantity=100.0)  # $10000
    snapshot = make_snapshot()
    
    limits = RiskLimits(
        correlation_clusters={"BTCUSDT": "CRYPTO_L1"},
        default_cluster_id="UNCLUSTERED",
    )
    
    decision = governor.evaluate(
        verdict=verdict,
        plan=plan,
        snapshot=snapshot,
        adapter_name="binance",
        now_ms=1000500,
        limits=limits,
    )
    
    assert decision.correlation_cluster_id == "UNCLUSTERED"


def test_warn_cluster_threshold():
    """Soft cluster limit → MANUAL_REVIEW"""
    governor = PositionExposureGovernor(
        window_store=WindowCounterStore(),
        circuit_breaker=CircuitBreakerState(),
    )
    
    verdict = make_verdict()
    plan = make_plan(symbol="ETHUSDT", quantity=5.0)  # $15000
    
    # BTC: $15000 (existing)
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
    
    # Cluster: 15000 + 15000 = 30000
    # Hard caps:
    # - Order notional: $15000 > $10000 (10%) → Need to increase to 16%
    # - Symbol position: $15000 > $10000 (10%) → Need to increase to 16%
    # - Net exposure: OK
    # Hard cluster cap: 40% ($40000) ✅
    # Soft cluster cap: 25% ($25000) ❌ (30000 > 25000)
    limits = RiskLimits(
        max_order_notional_pct_of_equity=0.16,  # Increase
        max_position_notional_pct_of_equity=0.35,  # Increase to 35% (30000 < 35000)
        max_total_net_exposure_pct_of_equity=0.35,  # Raise to avoid net cap (30000 < 35000)
        max_cluster_gross_exposure_pct_of_equity=0.40,  # Increase hard cap
        warn_cluster_gross_exposure_pct_of_equity=0.25,  # Soft at 25%
        correlation_clusters={
            "BTCUSDT": "CRYPTO_L1",
            "ETHUSDT": "CRYPTO_L1",
        },
    )
    
    decision = governor.evaluate(
        verdict=verdict,
        plan=plan,
        snapshot=snapshot,
        adapter_name="binance",
        now_ms=1000500,
        limits=limits,
    )
    
    assert decision.decision == Decision.REQUIRES_MANUAL_REVIEW
    assert ReasonCode.SOFT_WARN_CLUSTER_EXPOSURE in decision.reason_codes


def test_hard_cluster_threshold_block():
    """Hard cluster limit → BLOCK"""
    governor = PositionExposureGovernor(
        window_store=WindowCounterStore(),
        circuit_breaker=CircuitBreakerState(),
    )
    
    verdict = make_verdict()
    plan = make_plan(symbol="ADAUSDT", quantity=50000.0)  # 50000 ADA @ 0.5 = $25000
    
    # Existing SOL: $10000
    snapshot = make_snapshot(
        equity=100000.0,
        positions=[
            Position(
                symbol="SOLUSDT",
                side="LONG",
                quantity=100.0,
                avg_entry_price=100.0,
                mark_price=100.0,
                notional=10000.0,
            ),
        ],
    )
    
    # Both in "ALTCOIN" cluster
    # Cluster: 10000 + 25000 = 35000 > 30000 (30% cap)
    limits = RiskLimits(
        max_cluster_gross_exposure_pct_of_equity=0.30,
        correlation_clusters={
            "SOLUSDT": "ALTCOIN",
            "ADAUSDT": "ALTCOIN",
        },
    )
    
    decision = governor.evaluate(
        verdict=verdict,
        plan=plan,
        snapshot=snapshot,
        adapter_name="binance",
        now_ms=1000500,
        limits=limits,
    )
    
    assert decision.decision == Decision.BLOCK
    assert ReasonCode.CLUSTER_EXPOSURE_CAP_EXCEEDED in decision.reason_codes
