"""
EPOCH C: Intent → Order Conversion
Deterministic transformation of ExecutionIntent into atomic OrderPlan
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from .models import OrderPlan
from ..proposal.models import ExecutionIntent


class FatFingerError(Exception):
    """Fat-finger protection violation"""
    def __init__(self, message: str, code: str):
        self.message = message
        self.code = code
        super().__init__(message)


class ConversionConfig:
    """Configuration for conversion + fat-finger guards"""
    # Fat-finger limits
    MAX_NOTIONAL_PER_ORDER = 100_000  # $100k
    MAX_NOTIONAL_PER_INTENT = 500_000  # $500k
    MAX_POSITION_PCT = 0.25  # 25% of portfolio equity
    MAX_LEVERAGE = 3.0  # 3x (tier-based, override via config)
    MAX_PRICE_DEVIATION_PCT = 0.10  # ±10% from reference price
    
    # Precision
    PRICE_PRECISION = 8  # decimal places
    QTY_PRECISION = 8


def convert_intent_to_plan(
    intent: ExecutionIntent,
    approval_snapshot: Dict[str, Any],
    execution_snapshot: Dict[str, Any],
    risk_config: Optional[Dict[str, Any]] = None
) -> OrderPlan:
    """
    Deterministic conversion: ExecutionIntent → OrderPlan
    
    INVARIANTS:
    - Same intent + snapshots → same plan (reproducible)
    - Fat-finger checks MUST pass (BLOCK on violation)
    - clientOrderId deterministic (intent_id:plan_id:order_idx:timestamp)
    
    Args:
        intent: ExecutionIntent (APPROVED proposal)
        approval_snapshot: Governance snapshot at approval time
        execution_snapshot: Market + portfolio snapshot at execution time
        risk_config: Optional risk configuration overrides
    
    Returns:
        OrderPlan with deterministic order array
    
    Raises:
        FatFingerError: If any fat-finger guard fails
    """
    config = ConversionConfig()
    if risk_config:
        # Override defaults with tier-based limits
        config.MAX_POSITION_PCT = risk_config.get("max_position_pct", config.MAX_POSITION_PCT)
        config.MAX_LEVERAGE = risk_config.get("max_leverage", config.MAX_LEVERAGE)
    
    # Extract plan snapshot from intent
    plan = intent.plan_snapshot  # {entry_zone_low, entry_zone_high, take_profit_targets, stop_loss, max_slippage_percent}
    execution_params = intent.execution_params or {}
    
    # Extract execution context
    size_usd = execution_params.get("size_usd", 10000.0)
    execution_strategy = execution_params.get("execution_strategy", "MARKET")
    ttl_seconds = execution_params.get("ttl_seconds", 300)
    
    # Market data from execution snapshot
    market_data = execution_snapshot.get("market_data", {})
    reference_price = market_data.get("mid_price")
    
    # Portfolio data
    portfolio = execution_snapshot.get("portfolio", {})
    equity_usd = portfolio.get("equity_usd")
    
    # Fail-closed: missing reference data → BLOCK in REAL mode
    run_mode = execution_snapshot.get("governance", {}).get("run_mode", "dry")
    if run_mode == "real":
        if not reference_price:
            raise FatFingerError("Missing reference price (mid_price) - BLOCKED in REAL mode", "MISSING_REFERENCE_PRICE")
        if not equity_usd:
            raise FatFingerError("Missing portfolio equity - BLOCKED in REAL mode", "MISSING_EQUITY")
    
    # Use mid price as fallback reference
    if not reference_price:
        reference_price = (plan["entry_zone_low"] + plan["entry_zone_high"]) / 2
    if not equity_usd:
        equity_usd = 10000.0  # Default fallback for DRY mode
    
    # Determine entry order parameters
    asset = approval_snapshot.get("asset", "BTC/USDT")
    action = approval_snapshot.get("action", "BUY")  # BUY | SELL
    
    if execution_strategy == "MARKET":
        entry_price = reference_price  # Use mid price for estimation
        entry_order_style = "MARKET"
        entry_order_price = None  # MARKET orders don't have price
    else:  # LIMIT
        # Use entry zone boundary (buy at low, sell at high)
        entry_price = plan["entry_zone_low"] if action == "BUY" else plan["entry_zone_high"]
        entry_order_style = "LIMIT"
        entry_order_price = round(entry_price, config.PRICE_PRECISION)
    
    # Calculate quantity
    quantity = size_usd / entry_price
    quantity = round(quantity, config.QTY_PRECISION)
    
    # Fat-finger checks
    _fat_finger_checks(
        quantity=quantity,
        entry_price=entry_price,
        reference_price=reference_price,
        size_usd=size_usd,
        equity_usd=equity_usd,
        take_profit_targets=plan.get("take_profit_targets", []),
        config=config
    )
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # BLOCKER A FIX: UUIDv5 Deterministic plan_id (36 chars)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Schema constraint: order_plans.id is String(36)
    # Old approach: plan_id = f"plan_{intent.id}" → 41 chars (CRASH)
    # New approach: UUIDv5 deterministic hash → exactly 36 chars
    
    # Define constant namespace UUID for Plans (deterministic seed)
    NAMESPACE_PLANS = uuid.UUID("8f3e5a7b-4c9d-4e2a-b1f6-3d8c7e5a9b2f")
    
    plan_version = 1  # Will increment if plan is superseded
    
    # Generate deterministic plan_id using UUIDv5
    # Formula: uuid.uuid5(namespace, f"{intent.id}:{plan_version}")
    # Result: 36-character UUID string, stable across restarts/machines
    plan_id = str(uuid.uuid5(NAMESPACE_PLANS, f"{intent.id}:{plan_version}"))
    
    # Verify length (MUST be 36 for String(36) schema)
    assert len(plan_id) == 36, f"plan_id length {len(plan_id)} != 36 (schema mismatch)"
    
    # clientOrderId MUST be deterministic and stable across retries
    # Rule: {intent_id}:{plan_version}:{order_index}
    # NO timestamps, NO random values
    
    # Extract reduce_only from execution_params (default False)
    reduce_only_intent = execution_params.get("reduce_only", False)
    
    # Build order array
    orders = []
    
    # Order 0: Entry
    orders.append({
        "order_index": 0,
        "order_type": "ENTRY",
        "side": action,  # BUY | SELL
        "symbol": asset,
        "quantity": quantity,
        "price": entry_order_price,
        "order_style": entry_order_style,
        "time_in_force": "GTC" if entry_order_style == "LIMIT" else "IOC",
        "client_order_id": f"{intent.id}:{plan_version}:0",  # DETERMINISTIC
        "dependencies": [],  # No dependencies
        "ttl_seconds": ttl_seconds,
        "reduce_only": reduce_only_intent,  # Propagate from intent
        "constraints": {
            "min_qty": 0.001,  # Exchange-specific, should come from adapter
            "max_qty": 10.0,
            "tick_size": 0.01,
            "step_size": 0.00001
        }
    })
    
    # Orders 1..N: Take-Profit Ladder
    tp_targets = plan.get("take_profit_targets", [])
    tp_side = "SELL" if action == "BUY" else "BUY"
    quantity_per_tp = quantity / len(tp_targets) if tp_targets else 0
    
    for i, tp_price in enumerate(tp_targets):
        orders.append({
            "order_index": i + 1,
            "order_type": f"TP{i + 1}",
            "side": tp_side,
            "symbol": asset,
            "quantity": round(quantity_per_tp, config.QTY_PRECISION),
            "price": round(tp_price, config.PRICE_PRECISION),
            "order_style": "LIMIT",
            "time_in_force": "GTC",
            "client_order_id": f"{intent.id}:{plan_version}:{i + 1}",  # DETERMINISTIC
            "dependencies": [0],  # Depends on entry FILLED
            "ttl_seconds": ttl_seconds,
            "reduce_only": True,  # Exit orders ALWAYS reduce_only
            "constraints": {
                "min_qty": 0.001,
                "max_qty": 10.0,
                "tick_size": 0.01,
                "step_size": 0.00001
            }
        })
    
    # Order N+1: Stop-Loss
    sl_price = plan.get("stop_loss")
    if sl_price:
        sl_index = len(tp_targets) + 1
        orders.append({
            "order_index": sl_index,
            "order_type": "SL",
            "side": tp_side,  # Same side as TP (close position)
            "symbol": asset,
            "quantity": quantity,  # Full position
            "price": round(sl_price, config.PRICE_PRECISION),
            "order_style": "STOP_LOSS",
            "time_in_force": "GTC",
            "client_order_id": f"{intent.id}:{plan_version}:{sl_index}",  # DETERMINISTIC
            "dependencies": [0],  # Depends on entry FILLED
            "ttl_seconds": ttl_seconds,
            "reduce_only": True,  # Exit orders ALWAYS reduce_only
            "constraints": {
                "min_qty": 0.001,
                "max_qty": 10.0,
                "tick_size": 0.01,
                "step_size": 0.00001
            }
        })
    
    # Calculate estimates
    total_estimated_cost = size_usd
    estimated_slippage = plan.get("max_slippage_percent", 0.5) / 100  # Convert % to decimal
    estimated_market_impact = size_usd / market_data.get("orderbook_depth_1pct_usd", 100000) if market_data.get("orderbook_depth_1pct_usd") else 0.01
    
    # Create OrderPlan (model instance will compute plan_hash externally)
    order_plan = OrderPlan(
        id=plan_id,  # DETERMINISTIC
        execution_intent_id=intent.id,
        plan_hash="",  # Will be computed by canonicalization service
        plan_version=plan_version,
        orders=orders,
        total_estimated_cost=total_estimated_cost,
        estimated_slippage=estimated_slippage,
        estimated_market_impact=estimated_market_impact,
        created_at=datetime.utcnow(),  # Metadata only, NOT in hash
        ttl_seconds=ttl_seconds
    )
    
    return order_plan


def _fat_finger_checks(
    quantity: float,
    entry_price: float,
    reference_price: float,
    size_usd: float,
    equity_usd: float,
    take_profit_targets: List[float],
    config: ConversionConfig
) -> None:
    """
    Fat-finger protection checks
    
    Raises:
        FatFingerError: If any check fails
    """
    # Check 1: Max notional per order
    entry_notional = quantity * entry_price
    if entry_notional > config.MAX_NOTIONAL_PER_ORDER:
        raise FatFingerError(
            f"Entry order notional ${entry_notional:,.2f} exceeds max ${config.MAX_NOTIONAL_PER_ORDER:,.2f}",
            "NOTIONAL_PER_ORDER_EXCEEDED"
        )
    
    # Check 2: Max notional per intent
    if size_usd > config.MAX_NOTIONAL_PER_INTENT:
        raise FatFingerError(
            f"Intent total ${size_usd:,.2f} exceeds max ${config.MAX_NOTIONAL_PER_INTENT:,.2f}",
            "NOTIONAL_PER_INTENT_EXCEEDED"
        )
    
    # Check 3: Max position vs equity
    position_pct = size_usd / equity_usd
    if position_pct > config.MAX_POSITION_PCT:
        raise FatFingerError(
            f"Position {position_pct:.1%} exceeds max {config.MAX_POSITION_PCT:.1%} of equity",
            "POSITION_PCT_EXCEEDED"
        )
    
    # Check 4: Price sanity (entry price vs reference)
    deviation = abs(entry_price - reference_price) / reference_price
    if deviation > config.MAX_PRICE_DEVIATION_PCT:
        raise FatFingerError(
            f"Entry price ${entry_price:,.2f} deviates {deviation:.1%} from reference ${reference_price:,.2f} (max {config.MAX_PRICE_DEVIATION_PCT:.1%})",
            "PRICE_DEVIATION_EXCEEDED"
        )
    
    # Check 5: TP price sanity
    for tp_price in take_profit_targets:
        tp_deviation = abs(tp_price - reference_price) / reference_price
        if tp_deviation > 0.50:  # TP targets can be further out (50% max)
            raise FatFingerError(
                f"TP price ${tp_price:,.2f} deviates {tp_deviation:.1%} from reference (max 50%)",
                "TP_PRICE_EXCESSIVE"
            )
