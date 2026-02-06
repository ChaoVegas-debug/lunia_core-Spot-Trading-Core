"""
Epoch C.1: Retry Guard Tests

Tests deterministic retry logic for network errors only.
"""
import pytest

from lunia_core.app.services.execution_bridge.models import OrderPlan, OrderSide, ExecutionResult
from lunia_core.app.services.execution_bridge.guards.retry_guard import RetryGuard


class MockAdapter:
    """Mock adapter that simulates errors"""
    
    def __init__(self, error_sequence):
        """
        Args:
            error_sequence: List of error codes to return (None = success)
                Example: ["NETWORK_ERROR", "NETWORK_ERROR", None] = fail twice, succeed third
        """
        self.error_sequence = error_sequence
        self.call_count = 0
        self.name = "mock_adapter"
    
    def place_order(self, plan: OrderPlan) -> ExecutionResult:
        error_code = self.error_sequence[min(self.call_count, len(self.error_sequence) - 1)]
        self.call_count += 1
        
        if error_code is None:
            # Success
            return ExecutionResult(
                plan_id=plan.id,
                verdict_id=plan.verdict_id,
                executed=True,
                exchange_order_id=f"ORDER-{self.call_count}",
                filled_qty=plan.quantity,
                avg_price=50000.0,
                error_code=None,
                error_detail=None
            )
        else:
            # Error
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


class TestNetworkErrorRetries:
    """Test retry on network errors"""
    
    def test_network_error_retries_up_to_max(self):
        """NETWORK_ERROR → retry up to 2 times (3 total attempts)"""
        # Fail twice, succeed third time
        adapter = MockAdapter(["NETWORK_ERROR", "NETWORK_ERROR", None])
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
        assert adapter.call_count == 3  # 1 initial + 2 retries
        print(f"✅ Network error retried: {adapter.call_count} attempts")
    
    def test_network_error_all_retries_exhausted(self):
        """All retries fail → return final error"""
        # All attempts fail
        adapter = MockAdapter(["NETWORK_ERROR", "NETWORK_ERROR", "NETWORK_ERROR"])
        guard = RetryGuard()
        
        plan = OrderPlan(
            verdict_id="test",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            quantity=0.001,
            sizing_logic="Test"
        )
        
        result = guard.execute_with_retry(adapter, plan)
        
        assert result.executed == False
        assert result.error_code == "NETWORK_ERROR"
        assert adapter.call_count == 3  # 1 initial + 2 retries
        print("✅ All retries exhausted → return error")


class TestExchangeRejectionNoRetry:
    """Test NO retry on exchange rejections"""
    
    def test_insufficient_funds_no_retry(self):
        """INSUFFICIENT_FUNDS → NO retry"""
        adapter = MockAdapter(["INSUFFICIENT_FUNDS"])
        guard = RetryGuard()
        
        plan = OrderPlan(
            verdict_id="test",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            quantity=0.001,
            sizing_logic="Test"
        )
        
        result = guard.execute_with_retry(adapter, plan)
        
        assert result.executed == False
        assert result.error_code == "INSUFFICIENT_FUNDS"
        assert adapter.call_count == 1  # NO retry
        print("✅ INSUFFICIENT_FUNDS → NO retry")
    
    def test_rate_limit_no_retry(self):
        """RATE_LIMIT → NO retry"""
        adapter = MockAdapter(["RATE_LIMIT"])
        guard = RetryGuard()
        
        plan = OrderPlan(
            verdict_id="test",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            quantity=0.001,
            sizing_logic="Test"
        )
        
        result = guard.execute_with_retry(adapter, plan)
        
        assert result.executed == False
        assert result.error_code == "RATE_LIMIT"
        assert adapter.call_count == 1  # NO retry
        print("✅ RATE_LIMIT → NO retry")


class TestRetryBackoffDeterministic:
    """Test deterministic backoff timing"""
    
    def test_backoff_schedule(self):
        """Backoff schedule: [1s, 2s]"""
        guard = RetryGuard()
        
        assert guard.BACKOFF_SCHEDULE == [1.0, 2.0]
        assert guard.MAX_RETRIES == 2
        print("✅ Backoff schedule is deterministic: [1s, 2s]")


class TestRetryJournaling:
    """Test retry attempts are journaled"""
    
    def test_retry_attempts_journaled(self):
        """All retry attempts logged via callback"""
        journal_log = []
        
        def journal_callback(event_type, plan_id, detail, metadata):
            journal_log.append({
                "event_type": event_type,
                "plan_id": plan_id,
                "detail": detail,
                "retry_attempt": metadata.get("retry_attempt")
            })
        
        # Fail twice, succeed third
        adapter = MockAdapter(["NETWORK_ERROR", "NETWORK_ERROR", None])
        guard = RetryGuard(journal_callback=journal_callback)
        
        plan = OrderPlan(
            verdict_id="test",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            quantity=0.001,
            sizing_logic="Test"
        )
        
        result = guard.execute_with_retry(adapter, plan)
        
        # Should have journaled 2 retry attempts
        assert len(journal_log) == 2
        assert all(e["event_type"] == "RETRY_ATTEMPT" for e in journal_log)
        assert journal_log[0]["retry_attempt"] == 1
        assert journal_log[1]["retry_attempt"] == 2
        
        print(f"✅ Retry attempts journaled: {len(journal_log)} events")
