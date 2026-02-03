"""
EPOCH C Phase 5: Orphan Position Guard Tests
Tests deadline policy, protection criteria, Safety Valve, DRY honesty, idempotency
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, MagicMock

# Import Orphan Guard
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.execution.orphan_guard import OrphanPositionGuard, OrphanReasonCode, ORPHAN_DEADLINE_SEC


# Helpers

def create_entry_order(client_order_id="intent_001:1:ENTRY:0", side="BUY"):
    return {
        "order_type": "ENTRY",
        "client_order_id": client_order_id,
        "side": side,
        "symbol": "BTC/USDT",
        "quantity": 0.1
    }


def create_sl_order(client_order_id="intent_001:1:SL:0"):
    return {
        "order_type": "SL",
        "client_order_id": client_order_id,
        "side": "SELL",
        "symbol": "BTC/USDT",
        "quantity": 0.1
    }


def create_execution(client_order_id, status, filled_at=None, filled_qty=0):
    return {
        "client_order_id": client_order_id,
        "status": status,
        "filled_at": filled_at.isoformat() if filled_at else None,
        "filled_qty": filled_qty
    }


def create_plan(asset="BTC/USDT", orders=None, plan_version=1):
    return {
        "id": f"plan_{plan_version}",
        "asset": asset,
        "plan_version": plan_version,
        "orders": orders or []
    }


def create_governance_snapshot(global_stop=False, system_mode="MANUAL"):
    return {
        "global_stop": global_stop,
        "system_mode": system_mode,
        "airlock_status": "ARMED"
    }


def create_position_state(position_qty=0.1, entry_filled_qty=0.1, symbol="BTC/USDT"):
    return {
        "position_qty": position_qty,
        "entry_filled_qty": entry_filled_qty,
        "symbol": symbol
    }


def create_mock_adapter():
    adapter = Mock()
    adapter.submit_order = Mock(return_value={"orderId": "12345", "status": "NEW"})
    return adapter


def create_mock_audit_emit():
    return Mock()


def create_mock_sanitize():
    return lambda x: x  # Pass-through


# Tests

def test_no_entry_order():
    """No Entry order → no orphan"""
    guard = OrphanPositionGuard()
    
    result = guard.evaluate_and_act(
        intent_id="intent_001",
        plan=create_plan(orders=[]),  # No orders
        order_executions=[],
        run_mode="real",
        governance_snapshot=create_governance_snapshot(),
        position_state=create_position_state(),
        now_utc=datetime.now(timezone.utc),
        adapter=create_mock_adapter(),
        audit_emit=create_mock_audit_emit(),
        sanitize_exchange_response=create_mock_sanitize()
    )
    
    assert result["is_orphan"] is False
    assert result["decision"] == "NOOP"
    assert "NO_ENTRY_ORDER" in result["reason_codes"]


def test_entry_not_filled():
    """Entry exists but not filled → no orphan"""
    guard = OrphanPositionGuard()
    
    entry_order = create_entry_order()
    plan = create_plan(orders=[entry_order, create_sl_order()])
    
    # Entry execution in PENDING status
    executions = [
        create_execution(entry_order["client_order_id"], "PENDING")
    ]
    
    result = guard.evaluate_and_act(
        intent_id="intent_001",
        plan=plan,
        order_executions=executions,
        run_mode="real",
        governance_snapshot=create_governance_snapshot(),
        position_state=create_position_state(),
        now_utc=datetime.now(timezone.utc),
        adapter=create_mock_adapter(),
        audit_emit=create_mock_audit_emit(),
        sanitize_exchange_response=create_mock_sanitize()
    )
    
    assert result["is_orphan"] is False
    assert result["decision"] == "NOOP"
    assert OrphanReasonCode.ENTRY_NOT_FILLED in result["reason_codes"]


def test_entry_filled_within_deadline_sl_missing():
    """Entry filled <10s ago, SL missing → not orphan yet (within deadline)"""
    guard = OrphanPositionGuard()
    
    now = datetime.now(timezone.utc)
    filled_at = now - timedelta(seconds=5)  # 5s ago (within 10s deadline)
    
    entry_order = create_entry_order()
    sl_order = create_sl_order()
    plan = create_plan(orders=[entry_order, sl_order])
    
    executions = [
        create_execution(entry_order["client_order_id"], "FILLED", filled_at=filled_at, filled_qty=0.1),
        # SL not submitted yet
    ]
    
    result = guard.evaluate_and_act(
        intent_id="intent_001",
        plan=plan,
        order_executions=executions,
        run_mode="real",
        governance_snapshot=create_governance_snapshot(),
        position_state=create_position_state(),
        now_utc=now,
        adapter=create_mock_adapter(),
        audit_emit=create_mock_audit_emit(),
        sanitize_exchange_response=create_mock_sanitize()
    )
    
    assert result["is_orphan"] is False  # Still within deadline
    assert result["decision"] == "NOOP"
    assert OrphanReasonCode.SL_MISSING in result["reason_codes"]
    assert OrphanReasonCode.ORPHAN_WITHIN_DEADLINE in result["reason_codes"]


def test_entry_filled_deadline_exceeded_orphan_detected():
    """Entry filled >10s ago, SL missing → orphan detected"""
    guard = OrphanPositionGuard()
    
    now = datetime.now(timezone.utc)
    filled_at = now - timedelta(seconds=15)  # 15s ago (exceeds 10s deadline)
    
    entry_order = create_entry_order()
    sl_order = create_sl_order()
    plan = create_plan(orders=[entry_order, sl_order])
    
    executions = [
        create_execution(entry_order["client_order_id"], "FILLED", filled_at=filled_at, filled_qty=0.1),
        # SL not submitted
    ]
    
    audit_emit = create_mock_audit_emit()
    adapter = create_mock_adapter()
    
    result = guard.evaluate_and_act(
        intent_id="intent_001",
        plan=plan,
        order_executions=executions,
        run_mode="real",
        governance_snapshot=create_governance_snapshot(),
        position_state=create_position_state(position_qty=0.1, entry_filled_qty=0.1),
        now_utc=now,
        adapter=adapter,
        audit_emit=audit_emit,
        sanitize_exchange_response=create_mock_sanitize()
    )
    
    assert result["is_orphan"] is True
    assert result["protected"] is False
    assert result["decision"] == "EMERGENCY_CLOSE_SUBMITTED"
    assert OrphanReasonCode.ORPHAN_DEADLINE_EXCEEDED in result["reason_codes"]
    assert OrphanReasonCode.SL_MISSING in result["reason_codes"]
    
    # Verify adapter was called
    adapter.submit_order.assert_called_once()
    call_kwargs = adapter.submit_order.call_args.kwargs
    assert call_kwargs["side"] == "SELL"  # Opposite of BUY entry
    assert call_kwargs["order_type"] == "MARKET"
    assert call_kwargs["reduce_only"] is True
    assert call_kwargs["client_order_id"] == "intent_001:1:EMERGENCY_CLOSE"
    
    # Verify audit emitted
    assert audit_emit.call_count >= 2  # ORPHAN_POSITION_DETECTED + EMERGENCY_CLOSE_TRIGGERED + SUBMITTED


def test_sl_active_protects_position():
    """Entry filled, SL SUBMITTED → protected (no orphan)"""
    guard = OrphanPositionGuard()
    
    now = datetime.now(timezone.utc)
    filled_at = now - timedelta(seconds=15)  # 15s ago (exceeds deadline)
    
    entry_order = create_entry_order()
    sl_order = create_sl_order()
    plan = create_plan(orders=[entry_order, sl_order])
    
    executions = [
        create_execution(entry_order["client_order_id"], "FILLED", filled_at=filled_at, filled_qty=0.1),
        create_execution(sl_order["client_order_id"], "SUBMITTED")  # SL is active
    ]
    
    result = guard.evaluate_and_act(
        intent_id="intent_001",
        plan=plan,
        order_executions=executions,
        run_mode="real",
        governance_snapshot=create_governance_snapshot(),
        position_state=create_position_state(),
        now_utc=now,
        adapter=create_mock_adapter(),
        audit_emit=create_mock_audit_emit(),
        sanitize_exchange_response=create_mock_sanitize()
    )
    
    assert result["is_orphan"] is False
    assert result["protected"] is True
    assert result["decision"] == "NOOP"
    assert OrphanReasonCode.SL_ACTIVE in result["reason_codes"]


def test_tp_does_not_protect():
    """TP submitted but SL missing → still orphan (TP doesn't count as protection)"""
    guard = OrphanPositionGuard()
    
    now = datetime.now(timezone.utc)
    filled_at = now - timedelta(seconds=15)
    
    entry_order = create_entry_order()
    sl_order = create_sl_order()
    tp_order = {
        "order_type": "TP1",
        "client_order_id": "intent_001:1:TP1:0",
        "side": "SELL",
        "symbol": "BTC/USDT",
        "quantity": 0.05
    }
    plan = create_plan(orders=[entry_order, sl_order, tp_order])
    
    executions = [
        create_execution(entry_order["client_order_id"], "FILLED", filled_at=filled_at, filled_qty=0.1),
        create_execution(tp_order["client_order_id"], "SUBMITTED"),  # TP active (doesn't count)
        # SL missing
    ]
    
    audit_emit = create_mock_audit_emit()
    adapter = create_mock_adapter()
    
    result = guard.evaluate_and_act(
        intent_id="intent_001",
        plan=plan,
        order_executions=executions,
        run_mode="real",
        governance_snapshot=create_governance_snapshot(),
        position_state=create_position_state(position_qty=0.1, entry_filled_qty=0.1),
        now_utc=now,
        adapter=adapter,
        audit_emit=audit_emit,
        sanitize_exchange_response=create_mock_sanitize()
    )
    
    assert result["is_orphan"] is True
    assert result["decision"] == "EMERGENCY_CLOSE_SUBMITTED"
    assert OrphanReasonCode.SL_MISSING in result["reason_codes"]


def test_safety_valve_allows_emergency_close_with_global_stop():
    """global_stop=True + orphan + position exists → Safety Valve allows Emergency Close"""
    guard = OrphanPositionGuard()
    
    now = datetime.now(timezone.utc)
    filled_at = now - timedelta(seconds=15)
    
    entry_order = create_entry_order()
    sl_order = create_sl_order()
    plan = create_plan(orders=[entry_order, sl_order])
    
    executions = [
        create_execution(entry_order["client_order_id"], "FILLED", filled_at=filled_at, filled_qty=0.1),
        # SL missing
    ]
    
    audit_emit = create_mock_audit_emit()
    adapter = create_mock_adapter()
    
    result = guard.evaluate_and_act(
        intent_id="intent_001",
        plan=plan,
        order_executions=executions,
        run_mode="real",
        governance_snapshot=create_governance_snapshot(global_stop=True),  # Global stop active!
        position_state=create_position_state(position_qty=0.1, entry_filled_qty=0.1),
        now_utc=now,
        adapter=adapter,
        audit_emit=audit_emit,
        sanitize_exchange_response=create_mock_sanitize()
    )
    
    assert result["is_orphan"] is True
    assert result["decision"] == "EMERGENCY_CLOSE_SUBMITTED"  # Safety Valve allowed it
    assert OrphanReasonCode.GLOBAL_STOP_ACTIVE in result["reason_codes"]
    assert OrphanReasonCode.SAFETY_VALVE_ALLOWED in result["reason_codes"]
    
    # Verify adapter was called despite global_stop
    adapter.submit_order.assert_called_once()


def test_safety_valve_blocks_if_no_position():
    """global_stop=True + orphan but NO position → Safety Valve blocks"""
    guard = OrphanPositionGuard()
    
    now = datetime.now(timezone.utc)
    filled_at = now - timedelta(seconds=15)
    
    entry_order = create_entry_order()
    sl_order = create_sl_order()
    plan = create_plan(orders=[entry_order, sl_order])
    
    executions = [
        create_execution(entry_order["client_order_id"], "FILLED", filled_at=filled_at, filled_qty=0.1),
        # SL missing
    ]
    
    audit_emit = create_mock_audit_emit()
    adapter = create_mock_adapter()
    
    result = guard.evaluate_and_act(
        intent_id="intent_001",
        plan=plan,
        order_executions=executions,
        run_mode="real",
        governance_snapshot=create_governance_snapshot(global_stop=True),
        position_state=create_position_state(position_qty=0, entry_filled_qty=0.1),  # No position!
        now_utc=now,
        adapter=adapter,
        audit_emit=audit_emit,
        sanitize_exchange_response=create_mock_sanitize()
    )
    
    assert result["is_orphan"] is True
    assert result["decision"] == "EMERGENCY_CLOSE_BLOCKED"  # Safety Valve NOT eligible
    assert OrphanReasonCode.NO_POSITION_EXISTS in result["reason_codes"]
    assert OrphanReasonCode.SAFETY_VALVE_NOT_ELIGIBLE in result["reason_codes"]
    
    # Verify adapter was NOT called
    adapter.submit_order.assert_not_called()


def test_dry_mode_never_calls_adapter():
    """DRY mode → orphan detected, simulation audit, adapter NEVER called"""
    guard = OrphanPositionGuard()
    
    now = datetime.now(timezone.utc)
    filled_at = now - timedelta(seconds=15)
    
    entry_order = create_entry_order()
    sl_order = create_sl_order()
    plan = create_plan(orders=[entry_order, sl_order])
    
    executions = [
        create_execution(entry_order["client_order_id"], "FILLED", filled_at=filled_at, filled_qty=0.1),
        # SL missing
    ]
    
    audit_emit = create_mock_audit_emit()
    adapter = create_mock_adapter()
    
    result = guard.evaluate_and_act(
        intent_id="intent_001",
        plan=plan,
        order_executions=executions,
        run_mode="dry",  # DRY MODE
        governance_snapshot=create_governance_snapshot(),
        position_state=create_position_state(position_qty=0.1, entry_filled_qty=0.1),
        now_utc=now,
        adapter=adapter,
        audit_emit=audit_emit,
        sanitize_exchange_response=create_mock_sanitize()
    )
    
    assert result["is_orphan"] is True
    assert result["decision"] == "EMERGENCY_CLOSE_SIMULATED"  # Simulation only
    
    # Verify adapter was NEVER called
    adapter.submit_order.assert_not_called()
    
    # Verify simulation audit emitted
    audit_emit.assert_called_once()
    assert audit_emit.call_args.kwargs["event_type"] == "ORPHAN_POSITION_DETECTED_SIMULATION"


def test_idempotency_existing_emergency_close():
    """Existing Emergency Close client_order_id → idempotent reconcile (no re-submit)"""
    guard = OrphanPositionGuard()
    
    now = datetime.now(timezone.utc)
    filled_at = now - timedelta(seconds=15)
    
    entry_order = create_entry_order()
    sl_order = create_sl_order()
    plan = create_plan(orders=[entry_order, sl_order])
    
    executions = [
        create_execution(entry_order["client_order_id"], "FILLED", filled_at=filled_at, filled_qty=0.1),
        # SL missing
        # Emergency Close already exists
        create_execution("intent_001:1:EMERGENCY_CLOSE", "SUBMITTED")
    ]
    
    audit_emit = create_mock_audit_emit()
    adapter = create_mock_adapter()
    
    result = guard.evaluate_and_act(
        intent_id="intent_001",
        plan=plan,
        order_executions=executions,
        run_mode="real",
        governance_snapshot=create_governance_snapshot(),
        position_state=create_position_state(position_qty=0.1, entry_filled_qty=0.1),
        now_utc=now,
        adapter=adapter,
        audit_emit=audit_emit,
        sanitize_exchange_response=create_mock_sanitize()
    )
    
    assert result["is_orphan"] is True
    assert result["decision"] == "DETECTED"  # Already handled
    assert OrphanReasonCode.EMERGENCY_CLOSE_IDEMPOTENT_RECONCILE in result["reason_codes"]
    
    # Verify adapter was NOT called again
    adapter.submit_order.assert_not_called()


def test_adapter_failure_emits_blocked():
    """Adapter submit() raises exception → EMERGENCY_CLOSE_BLOCKED audit"""
    guard = OrphanPositionGuard()
    
    now = datetime.now(timezone.utc)
    filled_at = now - timedelta(seconds=15)
    
    entry_order = create_entry_order()
    sl_order = create_sl_order()
    plan = create_plan(orders=[entry_order, sl_order])
    
    executions = [
        create_execution(entry_order["client_order_id"], "FILLED", filled_at=filled_at, filled_qty=0.1),
        # SL missing
    ]
    
    audit_emit = create_mock_audit_emit()
    
    # Adapter that raises exception
    adapter = Mock()
    adapter.submit_order = Mock(side_effect=Exception("Network error"))
    
    result = guard.evaluate_and_act(
        intent_id="intent_001",
        plan=plan,
        order_executions=executions,
        run_mode="real",
        governance_snapshot=create_governance_snapshot(),
        position_state=create_position_state(position_qty=0.1, entry_filled_qty=0.1),
        now_utc=now,
        adapter=adapter,
        audit_emit=audit_emit,
        sanitize_exchange_response=create_mock_sanitize()
    )
    
    assert result["is_orphan"] is True
    assert result["decision"] == "EMERGENCY_CLOSE_BLOCKED"
    assert OrphanReasonCode.EMERGENCY_CLOSE_SUBMIT_FAILED in result["reason_codes"]
    assert "Network error" in result["metadata"]["error"]
    
    # Verify EMERGENCY_CLOSE_BLOCKED audit emitted
    blocked_calls = [call for call in audit_emit.call_args_list 
                     if call.kwargs.get("event_type") == "EMERGENCY_CLOSE_BLOCKED"]
    assert len(blocked_calls) == 1


def test_sell_entry_emergency_buy():
    """Entry SELL → Emergency Close BUY (opposite side)"""
    guard = OrphanPositionGuard()
    
    now = datetime.now(timezone.utc)
    filled_at = now - timedelta(seconds=15)
    
    entry_order = create_entry_order(side="SELL")  # SELL entry
    sl_order = create_sl_order()
    plan = create_plan(orders=[entry_order, sl_order])
    
    executions = [
        create_execution(entry_order["client_order_id"], "FILLED", filled_at=filled_at, filled_qty=0.1),
        # SL missing
    ]
    
    adapter = create_mock_adapter()
    
    result = guard.evaluate_and_act(
        intent_id="intent_001",
        plan=plan,
        order_executions=executions,
        run_mode="real",
        governance_snapshot=create_governance_snapshot(),
        position_state=create_position_state(position_qty=0.1, entry_filled_qty=0.1),
        now_utc=now,
        adapter=adapter,
        audit_emit=create_mock_audit_emit(),
        sanitize_exchange_response=create_mock_sanitize()
    )
    
    assert result["decision"] == "EMERGENCY_CLOSE_SUBMITTED"
    
    # Verify side is BUY (opposite of SELL entry)
    call_kwargs = adapter.submit_order.call_args.kwargs
    assert call_kwargs["side"] == "BUY"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
