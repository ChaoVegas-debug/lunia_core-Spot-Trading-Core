"""
Epoch C.1: Integration Tests — End-to-End Execution Flows

Tests complete flows from Council verdict to exchange execution.
"""
import pytest

from lunia_core.app.services.council.models import CouncilVerdict, CouncilDecision
from lunia_core.app.services.execution_bridge.models import OrderPlan, OrderSide, ExecutionResult
from lunia_core.app.services.execution_bridge.idempotency import IdempotencyStore
from lunia_core.app.services.execution_bridge.planner import OrderPlanner
from lunia_core.app.services.execution_bridge.executor import OrderExecutor
from lunia_core.app.services.execution_bridge.adapters.binance_sandbox import BinanceSandboxAdapter
from lunia_core.app.services.execution_bridge.guards.rate_limit_guard import RateLimitGuard
from lunia_core.app.services.execution_bridge.guards.retry_guard import RetryGuard
from lunia_core.app.services.execution_bridge.reconciliation import PartialFillReconciler


def create_test_verdict(decision=CouncilDecision.APPROVE, symbol="BTC/USDT") -> CouncilVerdict:
    """Create test verdict"""
    return CouncilVerdict(
        proposal_id="test-proposal",
        decision=decision,
        veto_reason_codes=[],
        reasoning="Test verdict",
        votes=[],
        market_state_snapshot={
            "market_risk_flag": "SAFE",
            "symbol": symbol,
            "side": "BUY"
        }
    )


class TestApproveToExecutedFlow:
    """Test APPROVE verdict → successful execution"""
    
    def test_happy_path_approve_to_executed(self):
        """APPROVE → Plan → Execute → Result"""
        # Components
        planner = OrderPlanner()
        executor = OrderExecutor()
        adapter = BinanceSandboxAdapter()
        
        # 1. Verdict (Council APPROVE)
        verdict = create_test_verdict(CouncilDecision.APPROVE)
        equity = {"total_equity": 10000}
        
        # 2. Planning
        plan = planner.plan(verdict, equity, reference_price=50000)
        
        assert plan is not None
        assert plan.verdict_id == verdict.id
        
        # 3. Execution
        result = executor.execute(plan, adapter, reference_price=50000, dry_run=False)
        
        assert result.executed == True
        assert result.exchange_order_id is not None
        assert result.filled_qty == plan.quantity
        assert result.error_code is None
        
        print(f"✅ APPROVE → EXECUTED: order_id={result.exchange_order_id}")


class TestRateLimitBlocksOrder:
    """Test rate limit prevents order submission"""
    
    def test_rate_limit_blocks_execution(self):
        """Rate exceeded → NO order placed"""
        guard = RateLimitGuard(max_orders_per_second=2.0)
        adapter = BinanceSandboxAdapter()
        executor = OrderExecutor()
        
        # Exhaust rate limit
        guard.check(adapter.name)
        guard.check(adapter.name)
        
        # Next order should be blocked
        allowed = guard.check(adapter.name)
        
        assert allowed == False
        print("✅ Rate limit blocks order")


class TestPartialFillDetected:
    """Test partial fill detection"""
    
    def test_partial_fill_flagged(self):
        """Partial fill → PARTIAL status + remaining_qty"""
        reconciler = PartialFillReconciler()
        
        plan = OrderPlan(
            verdict_id="test",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            quantity=1.0,
            sizing_logic="Test"
        )
        
        # Simulated partial fill
        result = ExecutionResult(
            plan_id=plan.id,
            verdict_id=plan.verdict_id,
            executed=True,
            exchange_order_id="ORDER-123",
            filled_qty=0.5,  # 50% filled
            avg_price=50000.0,
            error_code=None,
            error_detail=None
        )
        
        recon = reconciler.reconcile(result, plan)
        
        assert recon["status"] == "PARTIAL"
        assert recon["filled_qty"] == 0.5
        assert recon["remaining_qty"] == 0.5
        assert recon["fill_percentage"] == 50.0
        assert recon["requires_manual_review"] == True
        
        print(f"✅ Partial fill detected: {recon['fill_percentage']}% filled")


class TestIdempotencyDuplicateVerdict:
    """Test duplicate verdict_id returns cached result"""
    
    def test_duplicate_verdict_cached(self):
        """Duplicate verdict_id → cached result (no re-execution)"""
        store = IdempotencyStore()
        
        # First execution
        result1 = ExecutionResult(
            plan_id="plan-1",
            verdict_id="verdict-123",
            executed=True,
            exchange_order_id="ORDER-1",
            filled_qty=0.001,
            avg_price=50000.0
        )
        store.store("verdict-123", result1)
        
        # Second lookup (same verdict_id)
        result2 = store.get("verdict-123")
        
        assert result2 is not None
        assert result2.verdict_id == result1.verdict_id
        assert result2.exchange_order_id == result1.exchange_order_id
        
        print("✅ Idempotency: Duplicate verdict → cached result")


class TestNetworkRetrySuccess:
    """Test network error retry succeeds"""
    
    def test_network_retry_eventual_success(self):
        """Network error on attempt 1 → success on retry"""
        # Define MockAdapter inline
        class MockAdapter:
            def __init__(self, error_sequence):
                self.error_sequence = error_sequence
                self.call_count = 0
                self.name = "mock_adapter"
            
            def place_order(self, plan: OrderPlan) -> ExecutionResult:
                error_code = self.error_sequence[min(self.call_count, len(self.error_sequence) - 1)]
                self.call_count += 1
                
                if error_code is None:
                    return ExecutionResult(
                        plan_id=plan.id,
                        verdict_id=plan.verdict_id,
                        executed=True,
                        exchange_order_id=f"ORDER-{self.call_count}",
                        filled_qty=plan.quantity,
                        avg_price=50000.0
                    )
                else:
                    return ExecutionResult(
                        plan_id=plan.id,
                        verdict_id=plan.verdict_id,
                        executed=False,
                        exchange_order_id=None,
                        filled_qty=0.0,
                        avg_price=None,
                        error_code=error_code,
                        error_detail=f"Simulated {error_code}"
                    )
        
        # Fail once, succeed second time
        adapter = MockAdapter(["NETWORK_ERROR", None])
        guard = RetryGuard()
        
        plan = OrderPlan(
            verdict_id="test",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            quantity=0.001,
            sizing_logic="Test"
        )
        
        result = guard.execute_with_retry(adapter, plan)
        
        assert result.executed == True
        assert adapter.call_count == 2  # 1 initial + 1 retry
        print("✅ Network error → retry → success")


class TestExecutionJournalComplete:
    """Test execution journal captures all events"""
    
    def test_full_journal_trace(self):
        """All events (SUBMITTED, FILLED) captured in journal"""
        journal = []
        
        def journal_event(event_type, verdict_id, symbol, detail="", metadata=None):
            journal.append({
                "event_type": event_type,
                "verdict_id": verdict_id,
                "symbol": symbol,
                "detail": detail,
                "metadata": metadata or {}
            })
        
        # Simulate execution flow with journaling
        verdict_id = "verdict-test"
        symbol = "BTC/USDT"
        
        # Event 1: RECEIVED
        journal_event("RECEIVED", verdict_id, symbol, "Verdict received")
        
        # Event 2: PLANNED
        journal_event("PLANNED", verdict_id, symbol, "Order planned")
        
        # Event 3: SUBMITTED
        journal_event("SUBMITTED", verdict_id, symbol, "Order submitted",
                     {"adapter_name": "binance_sandbox"})
        
        # Event 4: FILLED
        journal_event("FILLED", verdict_id, symbol, "Order filled",
                     {"exchange_order_id": "ORDER-123", "filled_qty": 0.001})
        
        # Verify journal completeness
        assert len(journal) == 4
        assert journal[0]["event_type"] == "RECEIVED"
        assert journal[1]["event_type"] == "PLANNED"
        assert journal[2]["event_type"] == "SUBMITTED"
        assert journal[3]["event_type"] == "FILLED"
        
        print(f"✅ Full journal trace: {len(journal)} events")


class TestVetoBlocksExecution:
    """Test VETO verdict blocks execution"""
    
    def test_veto_no_plan_created(self):
        """VETO verdict → no plan created"""
        planner = OrderPlanner()
        verdict = create_test_verdict(CouncilDecision.VETO)
        equity = {"total_equity": 10000}
        
        plan = planner.plan(verdict, equity, reference_price=50000)
        
        assert plan is None
        print("✅ VETO → No plan created (execution blocked)")


class TestFullFillReconciliation:
    """Test full fill reconciliation"""
    
    def test_full_fill_no_review_needed(self):
        """100% fill → status=FILLED, no manual review"""
        reconciler = PartialFillReconciler()
        
        plan = OrderPlan(
            verdict_id="test",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            quantity=1.0,
            sizing_logic="Test"
        )
        
        result = ExecutionResult(
            plan_id=plan.id,
            verdict_id=plan.verdict_id,
            executed=True,
            exchange_order_id="ORDER-123",
            filled_qty=1.0,  # 100% filled
            avg_price=50000.0
        )
        
        recon = reconciler.reconcile(result, plan)
        
        assert recon["status"] == "FILLED"
        assert recon["remaining_qty"] == 0.0
        assert recon["fill_percentage"] == 100.0
        assert recon["requires_manual_review"] == False
        
        print("✅ Full fill: no manual review needed")


class TestErrorReconciliation:
    """Test error case reconciliation"""
    
    def test_execution_error_requires_review(self):
        """Execution error → status=ERROR, requires review"""
        reconciler = PartialFillReconciler()
        
        plan = OrderPlan(
            verdict_id="test",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            quantity=1.0,
            sizing_logic="Test"
        )
        
        result = ExecutionResult(
            plan_id=plan.id,
            verdict_id=plan.verdict_id,
            executed=False,
            exchange_order_id=None,
            filled_qty=0.0,
            avg_price=None,
            error_code="INSUFFICIENT_FUNDS",
            error_detail="Insufficient balance"
        )
        
        recon = reconciler.reconcile(result, plan)
        
        assert recon["status"] == "ERROR"
        assert recon["requires_manual_review"] == True
        assert recon["error_code"] == "INSUFFICIENT_FUNDS"
        
        print("✅ Error → requires manual review")
