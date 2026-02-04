"""
EPOCH C Phase 5: Reconciliation Engine Tests (Gate C)
Tests scan_stuck_orders, reconcile_one, backoff, hard vs soft classification
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta, timezone

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lunia_core.app.services.execution.reconciliation import ExecutionReconciler
from lunia_core.app.services.execution.models import OrderExecution, OrderExecutionStatus


def test_scan_stuck_orders_selects_submitting():
    """scan_stuck_orders selects SUBMITTING orders older than threshold"""
    adapter = Mock()
    reconciler = ExecutionReconciler(adapter=adapter)
    
    mock_session = Mock()
    
    # Create stuck order (created 60s ago)
    stuck_order = Mock(spec=OrderExecution)
    stuck_order.client_order_id = "stuck_order_001"
    stuck_order.status = OrderExecutionStatus.SUBMITTING
    stuck_order.created_at = datetime.now(timezone.utc) - timedelta(seconds=60)
    
    mock_session.query.return_value.filter.return_value.all.return_value = [stuck_order]
    
    with patch.object(reconciler, 'reconcile_one') as mock_reconcile_one:
        reconciler.scan_stuck_orders(mock_session)
        
        # VERIFY: reconcile_one was called for stuck order
        mock_reconcile_one.assert_called_once()
        assert mock_reconcile_one.call_args[0][1] == "stuck_order_001"


def test_reconcile_found_syncs_status():
    """Reconciliation FOUND: syncs local status to exchange status"""
    adapter = Mock()
    adapter.get_order.return_value = {
        "orderId": "exchange_12345",
        "status": "FILLED",
        "executedQty": "0.1"
    }
    
    reconciler = ExecutionReconciler(adapter=adapter)
    
    mock_session = Mock()
    
    # Order in SUBMITTING state
    order_exec = Mock(spec=OrderExecution)
    order_exec.client_order_id = "test_order_found"
    order_exec.status = OrderExecutionStatus.SUBMITTING
    order_exec.order_plan_id = "plan_001"
    order_exec.id = "exec_001"
    order_exec.filled_quantity = 0.0
    order_exec.filled_at = None
    
    mock_session.query.return_value.filter_by.return_value.with_for_update.return_value.first.return_value = order_exec
    
    with patch('app.services.execution.reconciliation.emit_execution_audit'):
        with patch('app.services.execution.reconciliation.sanitize_exchange_response', return_value={}):
            reconciler.reconcile_one(mock_session, "test_order_found", "real")
    
    # VERIFY: status updated to FILLED
    assert order_exec.status == OrderExecutionStatus.FILLED
    assert order_exec.filled_quantity == 0.1


def test_reconcile_not_found_marks_failed():
    """Reconciliation NOT FOUND: marks FAILED (safe terminal state)"""
    adapter = Mock()
    adapter.get_order.side_effect = Exception("Order not found (404)")
    
    reconciler = ExecutionReconciler(adapter=adapter)
    
    mock_session = Mock()
    
    order_exec = Mock(spec=OrderExecution)
    order_exec.client_order_id = "test_not_found"
    order_exec.status = OrderExecutionStatus.SUBMITTING
    order_exec.order_plan_id = "plan_002"
    order_exec.id = "exec_002"
    
    mock_session.query.return_value.filter_by.return_value.with_for_update.return_value.first.return_value = order_exec
    
    with patch('app.services.execution.reconciliation.emit_execution_audit'):
        reconciler.reconcile_one(mock_session, "test_not_found", "real")
    
    # VERIFY: status marked FAILED
    assert order_exec.status == OrderExecutionStatus.FAILED


def test_reconcile_timeout_keeps_submitting():
    """Reconciliation timeout: keeps SUBMITTING (ambiguous)"""
    adapter = Mock()
    adapter.get_order.side_effect = Exception("Connection timeout")
    
    reconciler = ExecutionReconciler(adapter=adapter)
    
    mock_session = Mock()
    
    order_exec = Mock(spec=OrderExecution)
    order_exec.client_order_id = "test_timeout"
    order_exec.status = OrderExecutionStatus.SUBMITTING
    order_exec.order_plan_id = "plan_003"
    order_exec.id = "exec_003"
    
    mock_session.query.return_value.filter_by.return_value.with_for_update.return_value.first.return_value = order_exec
    
    with patch('app.services.execution.reconciliation.emit_execution_audit'):
        reconciler.reconcile_one(mock_session, "test_timeout", "real")
    
    # VERIFY: status STILL SUBMITTING (not FAILED)
    assert order_exec.status == OrderExecutionStatus.SUBMITTING


def test_backoff_schedule():
    """Backoff prevents immediate retries"""
    adapter = Mock()
    reconciler = ExecutionReconciler(adapter=adapter)
    
    client_order_id = "test_backoff"
    
    # First attempt should be allowed
    assert reconciler._should_reconcile(client_order_id) is True
    
    # Record attempt
    reconciler._reconcile_attempts[client_order_id] = 1
    reconciler._last_reconcile[client_order_id] = datetime.now(timezone.utc)
    
    # Immediate retry should be blocked (backoff)
    assert reconciler._should_reconcile(client_order_id) is False
    
    # After backoff delay, should be allowed
    reconciler._last_reconcile[client_order_id] = datetime.now(timezone.utc) - timedelta(seconds=10)
    assert reconciler._should_reconcile(client_order_id) is True


def test_dry_mode_never_calls_adapter():
    """DRY mode: reconciliation never calls adapter.get_order"""
    adapter = Mock()
    reconciler = ExecutionReconciler(adapter=adapter)
    
    mock_session = Mock()
    
    order_exec = Mock(spec=OrderExecution)
    order_exec.client_order_id = "test_dry_reconcile"
    order_exec.status = OrderExecutionStatus.SUBMITTING
    order_exec.order_plan_id = "plan_dry"
    order_exec.id = "exec_dry"
    
    mock_session.query.return_value.filter_by.return_value.with_for_update.return_value.first.return_value = order_exec
    
    with patch('app.services.execution.reconciliation.emit_execution_audit'):
        reconciler.reconcile_one(mock_session, "test_dry_reconcile", "dry")
    
    # VERIFY: adapter.get_order was NEVER called
    adapter.get_order.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
