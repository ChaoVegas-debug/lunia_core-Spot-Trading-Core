"""
Epoch C: Execution Bridge Tests

Tests Council gate, sizing safety, idempotency, dry-run, and journal trace.
"""
import pytest

from lunia_core.app.services.council.models import CouncilVerdict, CouncilDecision
from lunia_core.app.services.execution_bridge.models import OrderPlan, OrderSide, ExecutionResult
from lunia_core.app.services.execution_bridge.idempotency import IdempotencyStore
from lunia_core.app.services.execution_bridge.planner import OrderPlanner
from lunia_core.app.services.execution_bridge.executor import OrderExecutor
from lunia_core.app.services.execution_bridge.adapters.paper import PaperAdapter


def create_test_verdict(decision=CouncilDecision.APPROVE, symbol="BTC/USDT", side="BUY") -> CouncilVerdict:
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
            "side": side
        }
    )


class TestCouncilGate:
    """Test Council approval gate"""
    
    def test_veto_blocks_planning(self):
        """VETO verdict should produce no plan"""
        planner = OrderPlanner()
        verdict = create_test_verdict(decision=CouncilDecision.VETO)
        equity = {"total_equity": 10000}
        
        plan = planner.plan(verdict, equity, reference_price=50000)
        
        assert plan is None
        print("✅ VETO verdict → No plan")
    
    def test_downgrade_blocks_planning(self):
        """DOWNGRADE verdict should produce no plan"""
        planner = OrderPlanner()
        verdict = create_test_verdict(decision=CouncilDecision.DOWNGRADE_TO_HOLD)
        equity = {"total_equity": 10000}
        
        plan = planner.plan(verdict, equity, reference_price=50000)
        
        assert plan is None
        print("✅ DOWNGRADE verdict → No plan")
    
    def test_approve_allows_planning(self):
        """APPROVE verdict should produce plan"""
        planner = OrderPlanner()
        verdict = create_test_verdict(decision=CouncilDecision.APPROVE)
        equity = {"total_equity": 10000}
        
        plan = planner.plan(verdict, equity, reference_price=50000)
        
        assert plan is not None
        assert plan.verdict_id == verdict.id
        print(f"✅ APPROVE verdict → Plan created (qty={plan.quantity})")


class TestSizingSafety:
    """Test sizing safety gates"""
    
    def test_missing_equity_blocks(self):
        """Missing equity should produce no plan"""
        planner = OrderPlanner()
        verdict = create_test_verdict()
        
        plan = planner.plan(verdict, equity_snapshot=None, reference_price=50000)
        
        assert plan is None
        print("✅ Missing equity → No plan (safety)")
    
    def test_missing_price_blocks(self):
        """Missing reference price should produce no plan"""
        planner = OrderPlanner()
        verdict = create_test_verdict()
        equity = {"total_equity": 10000}
        
        plan = planner.plan(verdict, equity, reference_price=None)
        
        assert plan is None
        print("✅ Missing price → No plan (safety)")
    
    def test_deterministic_sizing(self):
        """Sizing should be deterministic"""
        planner = OrderPlanner(default_risk_pct=0.01)
        verdict = create_test_verdict()
        equity = {"total_equity": 10000}
        
        plan = planner.plan(verdict, equity, reference_price=50000)
        
        # 1% of $10k = $100, $100 / $50k = 0.002 BTC
        assert plan.quantity == 0.002
        assert "Risk 1.0% of $10000.00 equity" in plan.sizing_logic
        print(f"✅ Deterministic sizing: {plan.quantity} BTC, logic={plan.sizing_logic}")


class TestIdempotency:
    """Test exactly-once execution"""
    
    def test_duplicate_verdict_cached(self):
        """Same verdict_id should return cached result"""
        store = IdempotencyStore()
        
        # First execution
        result1 = ExecutionResult(
            plan_id="plan-1",
            verdict_id="verdict-123",
            executed=True,
            exchange_order_id="ORDER-1"
        )
        store.store("verdict-123", result1)
        
        # Second lookup
        result2 = store.get("verdict-123")
        
        assert result2 is not None
        assert result2.verdict_id == result1.verdict_id
        assert result2.exchange_order_id == result1.exchange_order_id
        print("✅ Idempotency: Cached result returned")


class TestDryRun:
    """Test dry-run mode"""
    
    def test_dry_run_no_adapter_call(self):
        """Dry-run should not call adapter"""
        executor = OrderExecutor()
        plan = OrderPlan(
            verdict_id="test",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            quantity=0.002,
            sizing_logic="Test"
        )
        
        result = executor.execute(plan, adapter=None, reference_price=50000, dry_run=True)
        
        assert result.executed == True
        assert "DRY-RUN" in result.exchange_order_id
        print(f"✅ Dry-run: Simulated execution, order_id={result.exchange_order_id}")


class TestPaperAdapter:
    """Test paper trading adapter"""
    
    def test_paper_fill_deterministic(self):
        """Paper adapter should fill deterministically"""
        adapter = PaperAdapter()
        executor = OrderExecutor()
        plan = OrderPlan(
            verdict_id="test",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            quantity=0.002,
            sizing_logic="Test"
        )
        
        result = executor.execute(plan, adapter, reference_price=50000, dry_run=False)
        
        assert result.executed == True
        assert result.filled_qty == 0.002
        assert result.avg_price == 50000
        assert "PAPER" in result.exchange_order_id
        print(f"✅ Paper adapter: Filled {result.filled_qty} @ ${result.avg_price}")
