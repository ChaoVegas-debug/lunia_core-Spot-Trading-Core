"""
Epoch C.1: Binance Adapter Tests

Tests deterministic clientOrderId, error mapping, and sandbox behavior.
"""
import pytest
import hashlib

from lunia_core.app.services.execution_bridge.models import OrderPlan, OrderSide, ExecutionResult
from lunia_core.app.services.execution_bridge.adapters.binance_sandbox import BinanceSandboxAdapter


class TestDeterministicClientOrderId:
    """Test deterministic clientOrderId generation"""
    
    def test_same_plan_id_same_client_order_id(self):
        """Same plan_id → same clientOrderId"""
        adapter = BinanceSandboxAdapter()
        plan_id = "test-plan-123"
        
        coid1 = adapter._generate_client_order_id(plan_id)
        coid2 = adapter._generate_client_order_id(plan_id)
        
        assert coid1 == coid2
        print(f"✅ Deterministic: plan_id={plan_id} → clientOrderId={coid1}")
    
    def test_different_plan_id_different_client_order_id(self):
        """Different plan_id → different clientOrderId"""
        adapter = BinanceSandboxAdapter()
        
        coid1 = adapter._generate_client_order_id("plan-1")
        coid2 = adapter._generate_client_order_id("plan-2")
        
        assert coid1 != coid2
        print(f"✅ Different plans → different clientOrderIds")
    
    def test_client_order_id_format(self):
        """clientOrderId format: first 16 chars of SHA256"""
        adapter = BinanceSandboxAdapter()
        plan_id = "test-plan"
        
        coid = adapter._generate_client_order_id(plan_id)
        
        # Should be uppercase hex, 16 chars
        assert len(coid) == 16
        assert coid.isupper()
        assert all(c in "0123456789ABCDEF" for c in coid)
        
        # Verify matches SHA256 hash
        expected = hashlib.sha256(plan_id.encode()).hexdigest()[:16].upper()
        assert coid == expected
        print(f"✅ Valid format: {coid}")


class TestErrorMapping:
    """Test Binance error code mapping"""
    
    def test_rate_limit_error_mapping(self):
        """Binance -1003 → RATE_LIMIT"""
        adapter = BinanceSandboxAdapter()
        
        internal_code = adapter._map_error_code(-1003, "Too many requests")
        
        assert internal_code == "RATE_LIMIT"
        print("✅ -1003 → RATE_LIMIT")
    
    def test_insufficient_funds_mapping(self):
        """Binance -1013 → INSUFFICIENT_FUNDS"""
        adapter = BinanceSandboxAdapter()
        
        internal_code = adapter._map_error_code(-1013, "Insufficient balance")
        
        assert internal_code == "INSUFFICIENT_FUNDS"
        print("✅ -1013 → INSUFFICIENT_FUNDS")
    
    def test_invalid_symbol_mapping(self):
        """Binance -1121 → INVALID_SYMBOL"""
        adapter = BinanceSandboxAdapter()
        
        internal_code = adapter._map_error_code(-1121, "Invalid symbol")
        
        assert internal_code == "INVALID_SYMBOL"
        print("✅ -1121 → INVALID_SYMBOL")
    
    def test_unknown_error_mapping(self):
        """Unknown Binance error → UNKNOWN"""
        adapter = BinanceSandboxAdapter()
        
        internal_code = adapter._map_error_code(-9999, "Unknown error")
        
        assert internal_code == "UNKNOWN"
        print("✅ -9999 → UNKNOWN")


class TestSandboxHappyPath:
    """Test sandbox order placement"""
    
    def test_simulated_order_success(self):
        """Sandbox without API key simulates successful order"""
        adapter = BinanceSandboxAdapter()  # No API key
        
        plan = OrderPlan(
            verdict_id="test-verdict",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            quantity=0.001,
            sizing_logic="Test"
        )
        
        result = adapter.place_order(plan, reference_price=50000)
        
        assert result.executed == True
        assert result.exchange_order_id is not None
        assert "SANDBOX" in result.exchange_order_id
        assert result.filled_qty == plan.quantity
        assert result.avg_price > 0
        assert result.error_code is None
        
        print(f"✅ Simulated order: {result.exchange_order_id}")


class TestAdapterStateless:
    """Test adapter is stateless"""
    
    def test_multiple_calls_no_shared_state(self):
        """Multiple adapter instances don't share state"""
        adapter1 = BinanceSandboxAdapter()
        adapter2 = BinanceSandboxAdapter()
        
        plan = OrderPlan(
            verdict_id="test",
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            quantity=0.001,
            sizing_logic="Test"
        )
        
        result1 = adapter1.place_order(plan, reference_price=50000)
        result2 = adapter2.place_order(plan, reference_price=50000)
        
        # Both should succeed independently
        assert result1.executed == True
        assert result2.executed == True
        
        # Same plan → same clientOrderId (determinism)
        coid1 = adapter1._generate_client_order_id(plan.id)
        coid2 = adapter2._generate_client_order_id(plan.id)
        assert coid1 == coid2
        
        print("✅ Adapter is stateless")
