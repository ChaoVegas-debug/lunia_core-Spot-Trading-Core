"""
EPOCH C: Deterministic Canonicalization + Hashing
Ensures same intent → same plan (reproducible audit trail)
"""
import hashlib
import json
from typing import Any, Dict


def canonicalize(obj: Dict[str, Any]) -> str:
    """
    Canonical JSON serialization
    
    Rules:
    - Keys sorted alphabetically (recursive)
    - Compact (no whitespace)
    - 8-decimal precision for floats
    - Null fields omitted
    
    Args:
        obj: Dictionary to canonicalize
    
    Returns:
        Canonical JSON string
    """
    def _normalize_value(val: Any) -> Any:
        """Normalize value for canonical representation"""
        if val is None:
            return None  # Will be omitted
        elif isinstance(val, float):
            # Round to 8 decimal places
            return round(val, 8)
        elif isinstance(val, dict):
            # Recursively normalize dict, omit nulls
            return {k: _normalize_value(v) for k, v in val.items() if v is not None}
        elif isinstance(val, list):
            # Recursively normalize list elements
            return [_normalize_value(item) for item in val]
        else:
            return val
    
    normalized = _normalize_value(obj)
    
    # Serialize with sorted keys, compact
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=True
    )


def compute_hash(canonical_json: str) -> str:
    """
    Compute SHA256 hash of canonical JSON
    
    Args:
        canonical_json: Canonical JSON string
    
    Returns:
        Hexadecimal hash string (64 chars)
    """
    return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()


def compute_plan_hash(order_plan: Dict[str, Any]) -> str:
    """
    Compute plan_hash from OrderPlan
    
    Args:
        order_plan: OrderPlan dict with orders, metadata
    
    Returns:
        plan_hash (SHA256 hex)
    """
    orders = order_plan.get("orders", [])
    
    # FIX #2: Explicit sorting by order_index (MANDATORY)
    # Verify all orders have order_index
    for order in orders:
        if "order_index" not in order:
            raise IntegrityError("Order missing order_index - cannot compute deterministic hash")
        if not isinstance(order["order_index"], int):
            raise IntegrityError(f"order_index must be int, got {type(order['order_index'])}")
    
    # Check for duplicates
    order_indices = [o["order_index"] for o in orders]
    if len(order_indices) != len(set(order_indices)):
        raise IntegrityError(f"Duplicate order_index detected: {order_indices}")
    
    # Sort by order_index (deterministic ordering)
    orders_sorted = sorted(orders, key=lambda o: o["order_index"])
    
    # Extract fields for hashing (exclude id, created_at which vary)
    hashable = {
        "orders": orders_sorted,
        "total_estimated_cost": order_plan.get("total_estimated_cost"),
        "estimated_slippage": order_plan.get("estimated_slippage"),
        "plan_version": order_plan.get("plan_version", 1)
    }
    
    canonical = canonicalize(hashable)
    return compute_hash(canonical)


def compute_intent_hash(execution_intent: Dict[str, Any]) -> str:
    """
    Compute intent_hash from ExecutionIntent
    
    Args:
        execution_intent: Dict with execution_params, snapshots
    
    Returns:
        intent_hash (SHA256 hex)
    """
    hashable = {
        "execution_params": execution_intent.get("execution_params", {}),
        "governance_snapshot": execution_intent.get("governance_snapshot_at_approval", {}),
        "market_snapshot": execution_intent.get("market_snapshot_at_approval", {}),
        "portfolio_snapshot": execution_intent.get("portfolio_snapshot_at_approval", {})
    }
    
    canonical = canonicalize(hashable)
    return compute_hash(canonical)


def verify_plan_integrity(order_plan: Dict[str, Any], stored_hash: str) -> bool:
    """
    Verify OrderPlan integrity by recomputing hash
    
    Args:
        order_plan: OrderPlan dict
        stored_hash: Previously computed plan_hash
    
    Returns:
        True if hashes match (integrity verified)
    
    Raises:
        IntegrityError: If hashes don't match
    """
    recomputed_hash = compute_plan_hash(order_plan)
    if recomputed_hash != stored_hash:
        raise IntegrityError(
            f"Plan hash mismatch: stored={stored_hash}, recomputed={recomputed_hash}"
        )
    return True


class IntegrityError(Exception):
    """Hash integrity verification failed"""
    pass
