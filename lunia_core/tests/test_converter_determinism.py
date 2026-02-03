"""
Test converter determinism (FIX #1 verification)
"""
import pytest
from unittest.mock import Mock
from datetime import datetime

from app.services.execution.converter import convert_intent_to_plan, FatFingerError
from app.services.execution.canonicalization import compute_plan_hash


def test_deterministic_plan_id():
    """Same intent → same plan_id (no uuid4)"""
    # Mock intent
    intent = Mock()
    intent.id = "intent_abc123"
    intent.plan_snapshot = {
        "entry_zone_low": 43000,
        "entry_zone_high": 43100,
        "take_profit_targets": [44000, 45000],
        "stop_loss": 42000,
        "max_slippage_percent": 0.5
    }
    intent.execution_params = {
        "size_usd": 10000,
        "execution_strategy": "MARKET",
        "ttl_seconds": 300,
        "reduce_only": False
    }
    
    approval_snapshot = {
        "asset": "BTC/USDT",
        "action": "BUY"
    }
    
    execution_snapshot = {
        "governance": {"run_mode": "dry"},
        "market_data": {"mid_price": 43050},
        "portfolio": {"equity_usd": 50000}
    }
    
    # Convert twice
    plan1 = convert_intent_to_plan(intent, approval_snapshot, execution_snapshot)
    plan2 = convert_intent_to_plan(intent, approval_snapshot, execution_snapshot)
    
    # plan_id MUST be identical (UUIDv5 format, not string concat)
    assert plan1.id == plan2.id
    assert len(plan1.id) == 36  # UUIDv5 is exactly 36 chars
    print(f"✅ plan_id deterministic: {plan1.id}")


def test_deterministic_client_order_id():
    """Same intent → same clientOrderId(s) (no timestamps)"""
    intent = Mock()
    intent.id = "intent_xyz789"
    intent.plan_snapshot = {
        "entry_zone_low": 43000,
        "entry_zone_high": 43100,
        "take_profit_targets": [44000],
        "stop_loss": 42000,
        "max_slippage_percent": 0.5
    }
    intent.execution_params = {
        "size_usd": 10000,
        "execution_strategy": "MARKET",
        "ttl_seconds": 300,
        "reduce_only": False
    }
    
    approval_snapshot = {"asset": "BTC/USDT", "action": "BUY"}
    execution_snapshot = {
        "governance": {"run_mode": "dry"},
        "market_data": {"mid_price": 43050},
        "portfolio": {"equity_usd": 50000}
    }
    
    # Convert twice
    plan1 = convert_intent_to_plan(intent, approval_snapshot, execution_snapshot)
    plan2 = convert_intent_to_plan(intent, approval_snapshot, execution_snapshot)
    
    # Extract clientOrderIds
    client_order_ids_1 = [o["client_order_id"] for o in plan1.orders]
    client_order_ids_2 = [o["client_order_id"] for o in plan2.orders]
    
    # MUST be identical
    assert client_order_ids_1 == client_order_ids_2
    
    # Expected format: {intent_id}:{plan_version}:{order_index}
    assert client_order_ids_1[0] == "intent_xyz789:1:0"  # Entry
    assert client_order_ids_1[1] == "intent_xyz789:1:1"  # TP1
    assert client_order_ids_1[2] == "intent_xyz789:1:2"  # SL
    
    print(f"✅ clientOrderIds deterministic: {client_order_ids_1}")


def test_deterministic_plan_hash():
    """Same intent → same plan_hash"""
    intent = Mock()
    intent.id = "intent_hash_test"
    intent.plan_snapshot = {
        "entry_zone_low": 43000,
        "entry_zone_high": 43100,
        "take_profit_targets": [44000, 45000],
        "stop_loss": 42000,
        "max_slippage_percent": 0.5
    }
    intent.execution_params = {
        "size_usd": 10000,
        "execution_strategy": "LIMIT",
        "ttl_seconds": 300
    }
    
    approval_snapshot = {"asset": "BTC/USDT", "action": "BUY"}
    execution_snapshot = {
        "governance": {"run_mode": "dry"},
        "market_data": {"mid_price": 43050},
        "portfolio": {"equity_usd": 50000}
    }
    
    # Convert twice
    plan1 = convert_intent_to_plan(intent, approval_snapshot, execution_snapshot)
    plan2 = convert_intent_to_plan(intent, approval_snapshot, execution_snapshot)
    
    # Compute hashes
    plan1_dict = {
        "orders": plan1.orders,
        "total_estimated_cost": plan1.total_estimated_cost,
        "estimated_slippage": plan1.estimated_slippage,
        "plan_version": plan1.plan_version
    }
    plan2_dict = {
        "orders": plan2.orders,
        "total_estimated_cost": plan2.total_estimated_cost,
        "estimated_slippage": plan2.estimated_slippage,
        "plan_version": plan2.plan_version
    }
    
    hash1 = compute_plan_hash(plan1_dict)
    hash2 = compute_plan_hash(plan2_dict)
    
    # Hashes MUST be identical
    assert hash1 == hash2
    print(f"✅ plan_hash deterministic: {hash1}")


def test_fat_finger_rejects_still_work():
    """Fat-finger checks still reject oversized orders"""
    intent = Mock()
    intent.id = "intent_fat_finger"
    intent.plan_snapshot = {
        "entry_zone_low": 43000,
        "entry_zone_high": 43100,
        "take_profit_targets": [],
        "stop_loss": None,
        "max_slippage_percent": 0.5
    }
    intent.execution_params = {
        "size_usd": 200000,  # Exceeds MAX_NOTIONAL_PER_INTENT (500k limit set in config)
        "execution_strategy": "MARKET",
        "ttl_seconds": 300
    }
    
    approval_snapshot = {"asset": "BTC/USDT", "action": "BUY"}
    execution_snapshot = {
        "governance": {"run_mode": "dry"},
        "market_data": {"mid_price": 43050},
        "portfolio": {"equity_usd": 50000}  # 200k is 400% of equity - exceeds 25% limit
    }
    
    # Should raise FatFingerError
    with pytest.raises(FatFingerError) as exc_info:
        convert_intent_to_plan(intent, approval_snapshot, execution_snapshot)
    
    assert "NOTIONAL_PER_ORDER_EXCEEDED" in str(exc_info.value.code)
    print("✅ Fat-finger guard still works")


def test_reduce_only_propagation():
    """reduce_only propagates from intent to orders"""
    intent = Mock()
    intent.id = "intent_reduce_test"
    intent.plan_snapshot = {
        "entry_zone_low": 43000,
        "entry_zone_high": 43100,
        "take_profit_targets": [44000],
        "stop_loss": 42000,
        "max_slippage_percent": 0.5
    }
    intent.execution_params = {
        "size_usd": 10000,
        "execution_strategy": "MARKET",
        "ttl_seconds": 300,
        "reduce_only": True  # Intent is reduce-only
    }
    
    approval_snapshot = {"asset": "BTC/USDT", "action": "SELL"}
    execution_snapshot = {
        "governance": {"run_mode": "dry"},
        "market_data": {"mid_price": 43050},
        "portfolio": {"equity_usd": 50000}
    }
    
    plan = convert_intent_to_plan(intent, approval_snapshot, execution_snapshot)
    
    # Entry order should have reduce_only=True (from intent)
    assert plan.orders[0]["reduce_only"] is True
    
    # Exit orders (TP/SL) ALWAYS reduce_only=True
    assert plan.orders[1]["reduce_only"] is True  # TP
    assert plan.orders[2]["reduce_only"] is True  # SL
    
    print("✅ reduce_only propagated correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
