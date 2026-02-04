"""
Test canonicalization and hashing (FIX #2 verification)
"""
import pytest
from lunia_core.app.services.execution.canonicalization import (
    canonicalize, compute_hash, compute_plan_hash, IntegrityError
)


def test_explicit_order_sorting():
    """Orders sorted by order_index before hashing (shuffled → same hash)"""
    # Orders in natural order
    plan_ordered = {
        "orders": [
            {"order_index": 0, "symbol": "BTC/USDT", "qty": 0.1},
            {"order_index": 1, "symbol": "BTC/USDT", "qty": 0.05},
            {"order_index": 2, "symbol": "BTC/USDT", "qty": 0.05}
        ],
        "total_estimated_cost": 10000,
        "estimated_slippage": 0.005,
        "plan_version": 1
    }
    
    # Orders shuffled (reverse order)
    plan_shuffled = {
        "orders": [
            {"order_index": 2, "symbol": "BTC/USDT", "qty": 0.05},
            {"order_index": 1, "symbol": "BTC/USDT", "qty": 0.05},
            {"order_index": 0, "symbol": "BTC/USDT", "qty": 0.1}
        ],
        "total_estimated_cost": 10000,
        "estimated_slippage": 0.005,
        "plan_version": 1
    }
    
    hash1 = compute_plan_hash(plan_ordered)
    hash2 = compute_plan_hash(plan_shuffled)
    
    # Hashes MUST be identical (explicit sorting)
    assert hash1 == hash2
    print(f"✅ Shuffled orders → same hash: {hash1}")


def test_missing_order_index_fails():
    """Missing order_index raises IntegrityError"""
    plan_bad = {
        "orders": [
            {"symbol": "BTC/USDT", "qty": 0.1},  # Missing order_index
        ],
        "total_estimated_cost": 10000,
        "estimated_slippage": 0.005,
        "plan_version": 1
    }
    
    with pytest.raises(IntegrityError) as exc_info:
        compute_plan_hash(plan_bad)
    
    assert "missing order_index" in str(exc_info.value).lower()
    print("✅ Missing order_index detected")


def test_duplicate_order_index_fails():
    """Duplicate order_index raises IntegrityError"""
    plan_dup = {
        "orders": [
            {"order_index": 0, "symbol": "BTC/USDT", "qty": 0.1},
            {"order_index": 0, "symbol": "BTC/USDT", "qty": 0.05},  # Duplicate!
        ],
        "total_estimated_cost": 10000,
        "estimated_slippage": 0.005,
        "plan_version": 1
    }
    
    with pytest.raises(IntegrityError) as exc_info:
        compute_plan_hash(plan_dup)
    
    assert "duplicate" in str(exc_info.value).lower()
    print("✅ Duplicate order_index detected")


def test_volatile_fields_not_in_hash():
    """created_at, id not included in hash (metadata only)"""
    plan_base = {
        "id": "plan_abc",  # Should be excluded
        "orders": [{"order_index": 0, "qty": 0.1}],
        "total_estimated_cost": 10000,
        "estimated_slippage": 0.005,
        "plan_version": 1,
        "created_at": "2026-01-18T20:00:00Z"  # Should be excluded
    }
    
    plan_different_metadata = {
        "id": "plan_xyz",  # Different ID
        "orders": [{"order_index": 0, "qty": 0.1}],
        "total_estimated_cost": 10000,
        "estimated_slippage": 0.005,
        "plan_version": 1,
        "created_at": "2026-01-18T21:00:00Z"  # Different timestamp
    }
    
    hash1 = compute_plan_hash(plan_base)
    hash2 = compute_plan_hash(plan_different_metadata)
    
    # Hashes MUST be identical (id, created_at excluded)
    assert hash1 == hash2
    print(f"✅ Volatile fields excluded: {hash1}")


def test_canonicalization_numeric_precision():
    """Floats rounded to 8 decimals"""
    obj1 = {"price": 43250.123456789}  # 9 decimals
    obj2 = {"price": 43250.12345679}   # 8 decimals (rounded)
    
    canon1 = canonicalize(obj1)
    canon2 = canonicalize(obj2)
    
    # Should be identical after 8-decimal rounding
    assert canon1 == canon2
    print(f"✅ 8-decimal precision: {canon1}")


def test_hash_stability():
    """Same input → same hash (SHA256 deterministic)"""
    plan = {
        "orders": [{"order_index": 0, "symbol": "BTC/USDT", "qty": 0.1}],
        "total_estimated_cost": 10000.0,
        "estimated_slippage": 0.005,
        "plan_version": 1
    }
    
    hash1 = compute_plan_hash(plan)
    hash2 = compute_plan_hash(plan)
    hash3 = compute_plan_hash(plan)
    
    assert hash1 == hash2 == hash3
    assert len(hash1) == 64  # SHA256 hex length
    print(f"✅ Hash stable: {hash1}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
