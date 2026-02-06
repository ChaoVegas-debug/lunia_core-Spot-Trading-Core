"""
Epoch C.1: Rate Limit Guard Tests

Tests token bucket rate limiting per exchange.
"""
import pytest
import time

from lunia_core.app.services.execution_bridge.guards.rate_limit_guard import RateLimitGuard


class TestWithinRate:
    """Test orders within rate limit"""
    
    def test_within_rate_all_allowed(self):
        """4 orders in quick succession → all allowed (rate=5/sec)"""
        guard = RateLimitGuard(max_orders_per_second=5.0)
        adapter_name = "test_adapter"
        
        results = []
        for i in range(4):
            allowed = guard.check(adapter_name)
            results.append(allowed)
        
        assert all(results), "All 4 orders should be allowed"
        print(f"✅ Within rate: 4/5 orders allowed")
    
    def test_burst_capacity(self):
        """Burst capacity = 1 second worth of orders"""
        guard = RateLimitGuard(max_orders_per_second=5.0)
        adapter_name = "test_adapter"
        
        # Should allow up to 5 orders instantly
        results = []
        for i in range(5):
            allowed = guard.check(adapter_name)
            results.append(allowed)
        
        assert all(results), "All 5 orders should be allowed (burst capacity)"
        print("✅ Burst capacity works (5 orders instant)")


class TestExceedRate:
    """Test rate limit blocking"""
    
    def test_exceed_rate_blocked(self):
        """6th order in quick succession → blocked (rate=5/sec)"""
        guard = RateLimitGuard(max_orders_per_second=5.0)
        adapter_name = "test_adapter"
        
        # Consume all 5 tokens
        for i in range(5):
            guard.check(adapter_name)
        
        # 6th should be blocked
        allowed = guard.check(adapter_name)
        
        assert allowed == False, "6th order should be RATE LIMITED"
        print("✅ Rate limit: 6th order blocked")
    
    def test_token_bucket_refill(self):
        """Tokens refill over time"""
        guard = RateLimitGuard(max_orders_per_second=5.0)
        adapter_name = "test_adapter"
        
        # Consume 5 tokens
        for i in range(5):
            guard.check(adapter_name)
        
        # 6th should be blocked
        assert guard.check(adapter_name) == False
        
        # Wait for refill (>200ms should add 1 token)
        time.sleep(0.25)
        
        # Should now allow 1 more order
        allowed = guard.check(adapter_name)
        assert allowed == True, "Token should have refilled"
        print("✅ Tokens refill over time")


class TestPerExchangeIsolation:
    """Test rate limits are per-exchange"""
    
    def test_different_adapters_independent_buckets(self):
        """Adapter A rate limit doesn't affect Adapter B"""
        guard = RateLimitGuard(max_orders_per_second=5.0)
        
        # Exhaust Adapter A
        for i in range(5):
            guard.check("adapter_a")
        
        # Adapter A blocked
        assert guard.check("adapter_a") == False
        
        # Adapter B still has full capacity
        assert guard.check("adapter_b") == True
        
        print("✅ Per-exchange isolation works")
    
    def test_reset_bucket(self):
        """Reset clears bucket for adapter"""
        guard = RateLimitGuard(max_orders_per_second=5.0)
        adapter_name = "test"
        
        # Exhaust tokens
        for i in range(5):
            guard.check(adapter_name)
        
        assert guard.check(adapter_name) == False
        
        # Reset
        guard.reset(adapter_name)
        
        # Should be allowed again
        assert guard.check(adapter_name) == True
        print("✅ Reset bucket works")
