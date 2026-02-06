"""
Test Epoch C.2 — Governed Executor Integration

Tests for GovernedOrderExecutor wrapper with full execution flow.
"""
import pytest

from lunia_core.app.services.council.models import CouncilVerdict
from lunia_core.app.services.execution_bridge.adapters.paper import PaperAdapter
from lunia_core.app.services.execution_bridge.executor import OrderExecutor
from lunia_core.app.services.execution_bridge.governed_executor import (
    GovernedOrderExecutor,
    PortfolioSnapshotProvider,
)
from lunia_core.app.services.execution_bridge.planner import OrderPlanner
from lunia_core.app.services.risk_governor.config import RiskLimits
from lunia_core.app.services.risk_governor.governor import PositionExposureGovernor
from lunia_core.app.services.risk_governor.journal import RiskGovernorJournal
from lunia_core.app.services.risk_governor.models import PortfolioSnapshot, Position
from lunia_core.app.services.risk_governor.window_store import (
    CircuitBreakerState,
    WindowCounterStore,
)


class MockSnapshotProvider:
    """Mock portfolio snapshot provider for testing"""
    
    def __init__(self, snapshot: PortfolioSnapshot):
        self.snapshot = snapshot
    
    def get_snapshot(self) -> PortfolioSnapshot:
        return self.snapshot


class MockPlanner:
    """Mock planner for testing governed executor"""
    
    def __init__(self, quantity=0.01):
        self.quantity = quantity
    
    def plan(self, verdict, equity_snapshot, reference_price):
        """Create a test plan"""
        from lunia_core.app.services.execution_bridge.models import OrderPlan
        return OrderPlan(
            id=f"plan-{verdict.id[:8]}",
            verdict_id=verdict.id,
            symbol="BTCUSDT",
            side="BUY",
            quantity=self.quantity,
            sizing_logic="Fixed test quantity",
        )


def make_verdict(symbol="BTCUSDT", action="BUY", decision="APPROVE") -> CouncilVerdict:
    """Helper: Create test verdict"""
    return CouncilVerdict(
        id="test-verdict-123",
        proposal_id="test-proposal-123",
        decision=decision,
        reasoning="Test verdict rationale",
    )


def make_snapshot(equity=100000.0, positions=None) -> PortfolioSnapshot:
    """Helper: Create test snapshot"""
    return PortfolioSnapshot(
        as_of_ms=1000000,
        total_equity=equity,
        positions=positions or [],
        prices={"BTCUSDT": 50000.0, "ETHUSDT": 3000.0},
        pending=[],
    )


def make_governed_executor(snapshot: PortfolioSnapshot, limits: RiskLimits = None, quantity=0.01) -> GovernedOrderExecutor:
    """Helper: Create governed executor"""
    planner = MockPlanner(quantity=quantity)  # Use mock planner with configurable quantity
    executor = OrderExecutor()
    window_store = WindowCounterStore()
    circuit_breaker = CircuitBreakerState()
    governor = PositionExposureGovernor(window_store, circuit_breaker)
    journal = RiskGovernorJournal()
    snapshot_provider = MockSnapshotProvider(snapshot)
    
    return GovernedOrderExecutor(
        planner=planner,
        executor=executor,
        governor=governor,
        snapshot_provider=snapshot_provider,
        journal=journal,
        window_store=window_store,
        circuit_breaker=circuit_breaker,
        limits=limits or RiskLimits(),
    )


# =============================================================================
# DECISION ENFORCEMENT TESTS
# =============================================================================

def test_allow_executes():
    """ALLOW → executes normally"""
    snapshot = make_snapshot()
    gov_executor = make_governed_executor(snapshot)
    verdict = make_verdict()
    adapter = PaperAdapter()
    
    result = gov_executor.execute_governed(
        verdict=verdict,
        adapter=adapter,
        reference_price=50000.0,
        adapter_name="binance",
        equity={"total_equity": 100000.0},
        now_ms=1000500,
    )
    
    assert result.executed is True
    assert result.error_code is None


def test_block_returns_no_execution():
    """BLOCK → no execution, error result"""
    snapshot = make_snapshot(equity=100000.0)
    
    # Very restrictive limit (0.5% max order = $500)
    limits = RiskLimits(max_order_notional_pct_of_equity=0.005)
    
    # Order: 0.02 BTC @ 50000 = $1000 > $500 limit
    gov_executor = make_governed_executor(snapshot, limits, quantity=0.02)
    verdict = make_verdict()
    adapter = PaperAdapter()
    
    result = gov_executor.execute_governed(
        verdict=verdict,
        adapter=adapter,
        reference_price=50000.0,
        adapter_name="binance",
        equity={"total_equity": 100000.0},
        now_ms=1000500,
    )
    
    assert result.executed is False
    assert result.error_code == "GOVERNOR_BLOCK"
    assert result.filled_qty == 0


def test_manual_review_returns_no_execution():
    """MANUAL_REVIEW → no execution, error result"""
    snapshot = make_snapshot()
    
    # Soft limit violation
    limits = RiskLimits(
        max_order_notional_pct_of_equity=0.02,  # Hard: 2% = $2000
        warn_order_notional_pct_of_equity=0.005,  # Soft: 0.5% = $500
        soft_action="MANUAL_REVIEW",
    )
    
    # Order: 0.015 BTC @ 50000 = $750 > $500 soft but < $2000 hard
    gov_executor = make_governed_executor(snapshot, limits, quantity=0.015)
    verdict = make_verdict()
    adapter = PaperAdapter()
    
    result = gov_executor.execute_governed(
        verdict=verdict,
        adapter=adapter,
        reference_price=50000.0,
        adapter_name="binance",
        equity={"total_equity": 100000.0},
        now_ms=1000500,
    )
    
    assert result.executed is False
    assert result.error_code == "MANUAL_REVIEW_REQUIRED"


def test_downgrade_executes_dry_run():
    """DOWNGRADE → executes as dry run"""
    snapshot = make_snapshot()
    
    # Soft limit with downgrade action
    limits = RiskLimits(
        max_order_notional_pct_of_equity=0.02,  # Hard: 2% = $2000
        warn_order_notional_pct_of_equity=0.005,  # Soft: 0.5% = $500
        soft_action="DOWNGRADE_TO_DRY_RUN",
    )
    
    # Order: 0.015 BTC @ 50000 = $750 > $500 soft but < $2000 hard
    gov_executor = make_governed_executor(snapshot, limits, quantity=0.015)
    verdict = make_verdict()
    adapter = PaperAdapter()
    
    result = gov_executor.execute_governed(
        verdict=verdict,
        adapter=adapter,
        reference_price=50000.0,
        adapter_name="binance",
        equity={"total_equity": 100000.0},
        now_ms=1000500,
    )
    
    # Should execute (dry run), with "DRY-RUN-" prefix in order ID
    assert result.executed is True
    assert "DRY-RUN-" in result.exchange_order_id


def test_log_only_allows_but_records():
    """LOG_ONLY (shadow mode) → executes + journals"""
    snapshot = make_snapshot()
    limits = RiskLimits(shadow_mode=True)
    
    gov_executor = make_governed_executor(snapshot, limits)
    verdict = make_verdict()
    adapter = PaperAdapter()
    
    result = gov_executor.execute_governed(
        verdict=verdict,
        adapter=adapter,
        reference_price=50000.0,
        adapter_name="binance",
        equity={"total_equity": 100000.0},
        now_ms=1000500,
    )
    
    assert result.executed is True
    
    # Check journal recorded
    events = gov_executor.journal.get_all_events()
    assert len(events) == 1
    assert events[0].decision == "LOG_ONLY"


# =============================================================================
# JOURNAL TESTS
# =============================================================================

def test_journal_event_written():
    """All decisions are journaled"""
    snapshot = make_snapshot()
    gov_executor = make_governed_executor(snapshot)
    verdict = make_verdict()
    adapter = PaperAdapter()
    
    gov_executor.execute_governed(
        verdict=verdict,
        adapter=adapter,
        reference_price=50000.0,
        adapter_name="binance",
        equity={"total_equity": 100000.0},
        now_ms=1000500,
    )
    
    events = gov_executor.journal.get_all_events()
    assert len(events) == 1
    assert events[0].verdict_id == verdict.id
    assert events[0].symbol == "BTCUSDT"


# =============================================================================
# RATE LIMIT & CIRCUIT BREAKER TESTS
# =============================================================================

def test_orders_per_hour_blocks():
    """Exceeding orders/hour limit → BLOCK"""
    snapshot = make_snapshot()
    limits = RiskLimits(max_symbol_orders_per_hour=2)
    
    gov_executor = make_governed_executor(snapshot, limits)
    verdict = make_verdict()
    adapter = PaperAdapter()
    
    # Order 1 (allow)
    r1 = gov_executor.execute_governed(
        verdict=verdict,
        adapter=adapter,
        reference_price=50000.0,
        adapter_name="binance",
        equity={"total_equity": 100000.0},
        now_ms=1000000,
    )
    assert r1.executed is True
    
    # Order 2 (allow)
    r2 = gov_executor.execute_governed(
        verdict=verdict,
        adapter=adapter,
        reference_price=50000.0,
        adapter_name="binance",
        equity={"total_equity": 100000.0},
        now_ms=1001000,
    )
    assert r2.executed is True
    
    # Order 3 (block - rate limit)
    r3 = gov_executor.execute_governed(
        verdict=verdict,
        adapter=adapter,
        reference_price=50000.0,
        adapter_name="binance",
        equity={"total_equity": 100000.0},
        now_ms=1002000,
    )
    assert r3.executed is False
    assert r3.error_code == "GOVERNOR_BLOCK"


def test_circuit_breaker_trips():
    """Consecutive blocks → circuit breaker trip"""
    snapshot = make_snapshot()
    limits = RiskLimits(
        max_order_notional_pct_of_equity=0.001,  # Very restrictive
        circuit_breaker_consecutive_blocks=3,
    )
    
    gov_executor = make_governed_executor(snapshot, limits)
    verdict = make_verdict()
    adapter = PaperAdapter()
    
    # 3 consecutive blocks
    for i in range(3):
        result = gov_executor.execute_governed(
            verdict=verdict,
            adapter=adapter,
            reference_price=50000.0,
            adapter_name="binance",
            equity={"total_equity": 100000.0},
            now_ms=1000000 + i * 1000,
        )
        assert result.executed is False
    
    # Check circuit breaker state
    count = gov_executor.circuit_breaker.get_count("binance", "BTCUSDT")
    assert count == 3
    
    # Check journal shows halt recommended
    events = gov_executor.journal.get_all_events()
    last_event = events[-1]
    assert last_event.halt_recommended is True


def test_halt_recommended_flag():
    """Halt recommended flag set on circuit breaker trip"""
    snapshot = make_snapshot()
    limits = RiskLimits(
        max_order_notional_pct_of_equity=0.001,
        circuit_breaker_consecutive_blocks=2,
    )
    
    gov_executor = make_governed_executor(snapshot, limits)
    verdict = make_verdict()
    adapter = PaperAdapter()
    
    # Block 1
    gov_executor.execute_governed(
        verdict=verdict,
        adapter=adapter,
        reference_price=50000.0,
        adapter_name="binance",
        equity={"total_equity": 100000.0},
        now_ms=1000000,
    )
    
    # Block 2 → should trip breaker
    gov_executor.execute_governed(
        verdict=verdict,
        adapter=adapter,
        reference_price=50000.0,
        adapter_name="binance",
        equity={"total_equity": 100000.0},
        now_ms=1001000,
    )
    
    events = gov_executor.journal.get_all_events()
    assert events[-1].halt_recommended is True
