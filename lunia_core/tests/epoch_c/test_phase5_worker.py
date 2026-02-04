"""
EPOCH C Phase 5: Worker Submit Loop Tests (Gate C)
Tests DRY honesty, idempotency, ambiguous-state handling, orphan guard integration
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timezone

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lunia_core.app.services.execution.worker import ExecutionWorker
from lunia_core.app.services.execution.exceptions import HardError, SoftError
from lunia_core.app.services.execution.models import OrderExecution, OrderExecutionStatus, OrderPlan
from lunia_core.app.services.proposal.models import ExecutionIntent


def test_dry_mode_never_calls_adapter():
    """DRY mode: adapter submit_order NEVER called"""
    adapter = Mock()
    worker = ExecutionWorker(adapter=adapter, worker_id="test-worker")
    
    # Mock session and models
    with patch('app.services.execution.worker.get_session') as mock_get_session:
        mock_session = Mock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        
        # Mock intent and plan
        intent = Mock(spec=ExecutionIntent)
        intent.id = "intent_001"
        intent.run_mode = "dry"
        
        plan = Mock(spec=OrderPlan)
        plan.id = "plan_001"
        plan.execution_intent_id = "intent_001"
        plan.plan_version = 1
        plan.orders = [{
            "order_index": 0,
            "client_order_id": "test_order_001",
            "symbol": "BTC/USDT",
            "side": "BUY",
            "quantity": 0.1,
            "order_type": "ENTRY",
            "order_style": "MARKET"
        }]
        
        mock_session.query.return_value.filter_by.return_value.first.side_effect = [
            intent,  # First query for intent
            plan,    # Second query for plan
            None     # Third query for existing OrderExecution (idempotency check)
        ]
        
        # Mock governance gate
        with patch('app.services.execution.worker.ExecutionGovernanceGate') as mock_gate:
            mock_decision = Mock()
            mock_decision.decision = "ALLOW"
            mock_decision.reason_codes = []
            mock_decision.governance_snapshot = {}
            mock_gate.return_value.check.return_value = mock_decision
            
            # Mock orphan guard
            with patch('app.services.execution.worker.OrphanPositionGuard') as mock_orphan:
                mock_orphan.return_value.evaluate_and_act.return_value = {
                    "is_orphan": False,
                    "protected": True,
                    "decision": "NOOP",
                    "reason_codes": [],
                    "metadata": {}
                }
                
                # Mock audit
                with patch('app.services.execution.worker.emit_execution_audit'):
                    # Run one iteration
                    worker.run(max_iterations=1)
    
    # VERIFY: adapter.submit_order was NEVER called
    adapter.submit_order.assert_not_called()


def test_idempotency_existing_order_execution():
    """Existing OrderExecution prevents double submit"""
    adapter = Mock()
    worker = ExecutionWorker(adapter=adapter, worker_id="test-worker")
    
    client_order_id = "test_order_idempotent"
    
    with patch('app.services.execution.worker.get_session') as mock_get_session:
        mock_session = Mock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        
        intent = Mock(spec=ExecutionIntent)
        intent.id = "intent_002"
        intent.run_mode = "real"
        
        plan = Mock(spec=OrderPlan)
        plan.id = "plan_002"
        plan.execution_intent_id = "intent_002"
        plan.plan_version = 1
        plan.orders = [{
            "order_index": 0,
            "client_order_id": client_order_id,
            "symbol": "ETH/USDT",
            "side": "SELL",
            "quantity": 1.0,
            "order_type": "ENTRY",
            "order_style": "MARKET"
        }]
        
        # Existing OrderExecution (already FILLED)
        existing_exec = Mock(spec=OrderExecution)
        existing_exec.client_order_id = client_order_id
        existing_exec.status = OrderExecutionStatus.FILLED
        
        mock_session.query.return_value.filter_by.return_value.first.side_effect = [
            intent,
            plan,
            existing_exec  # Idempotency check finds existing
        ]
        
        with patch('app.services.execution.worker.ExecutionGovernanceGate') as mock_gate:
            mock_decision = Mock()
            mock_decision.decision = "ALLOW"
            mock_gate.return_value.check.return_value = mock_decision
            
            with patch('app.services.execution.worker.OrphanPositionGuard') as mock_orphan:
                mock_orphan.return_value.evaluate_and_act.return_value = {
                    "is_orphan": False,
                    "protected": True,
                    "decision": "NOOP",
                    "reason_codes": [],
                    "metadata": {}
                }
                
                with patch('app.services.execution.worker.emit_execution_audit'):
                    worker.run(max_iterations=1)
    
    # VERIFY: adapter.submit_order was NEVER called (idempotency prevented double submit)
    adapter.submit_order.assert_not_called()


def test_soft_error_keeps_submitting():
    """Soft error (timeout/network) keeps status=SUBMITTING, does NOT mark FAILED"""
    adapter = Mock()
    adapter.submit_order.side_effect = SoftError("Connection timeout")
    
    worker = ExecutionWorker(adapter=adapter, worker_id="test-worker")
    
    with patch('app.services.execution.worker.get_session') as mock_get_session:
        mock_session = Mock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        
        intent = Mock(spec=ExecutionIntent)
        intent.id = "intent_003"
        intent.run_mode = "real"
        
        plan = Mock(spec=OrderPlan)
        plan.id = "plan_003"
        plan.execution_intent_id = "intent_003"
        plan.plan_version = 1
        plan.orders = [{
            "order_index": 0,
            "client_order_id": "test_soft_error",
            "symbol": "BTC/USDT",
            "side": "BUY",
            "quantity": 0.1,
            "order_type": "ENTRY",
            "order_style": "MARKET"
        }]
        
        # Track created OrderExecution
        created_order_exec = None
        
        def mock_add(obj):
            nonlocal created_order_exec
            if isinstance(obj, OrderExecution):
                created_order_exec = obj
        
        mock_session.add = mock_add
        mock_session.query.return_value.filter_by.return_value.first.side_effect = [
            intent,
            plan,
            None  # No existing OrderExecution
        ]
        
        with patch('app.services.execution.worker.ExecutionGovernanceGate') as mock_gate:
            mock_decision = Mock()
            mock_decision.decision = "ALLOW"
            mock_gate.return_value.check.return_value = mock_decision
            
            with patch('app.services.execution.worker.OrphanPositionGuard') as mock_orphan:
                mock_orphan.return_value.evaluate_and_act.return_value = {
                    "is_orphan": False,
                    "protected": True,
                    "decision": "NOOP",
                    "reason_codes": [],
                    "metadata": {}
                }
                
                with patch('app.services.execution.worker.emit_execution_audit'):
                    try:
                        worker.run(max_iterations=1)
                    except:
                        pass  # Worker may raise, but we care about order_exec status
    
    # VERIFY: created OrderExecution status is SUBMITTING (NOT FAILED)
    assert created_order_exec is not None
    assert created_order_exec.status == OrderExecutionStatus.SUBMITTING


def test_orphan_guard_always_called():
    """Orphan guard is called after every order attempt (success/hard/soft)"""
    adapter = Mock()
    adapter.submit_order.return_value = {"orderId": "12345", "status": "NEW"}
    
    worker = ExecutionWorker(adapter=adapter, worker_id="test-worker")
    
    with patch('app.services.execution.worker.get_session') as mock_get_session:
        mock_session = Mock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        
        intent = Mock(spec=ExecutionIntent)
        intent.id = "intent_004"
        intent.run_mode = "real"
        
        plan = Mock(spec=OrderPlan)
        plan.id = "plan_004"
        plan.execution_intent_id = "intent_004"
        plan.plan_version = 1
        plan.orders = [{
            "order_index": 0,
            "client_order_id": "test_orphan_guard",
            "symbol": "BTC/USDT",
            "side": "BUY",
            "quantity": 0.1,
            "order_type": "ENTRY",
            "order_style": "MARKET"
        }]
        
        mock_session.query.return_value.filter_by.return_value.first.side_effect = [
            intent,
            plan,
            None  # No existing
        ]
        mock_session.query.return_value.filter_by.return_value.all.return_value = []  # No executions yet
        
        with patch('app.services.execution.worker.ExecutionGovernanceGate') as mock_gate:
            mock_decision = Mock()
            mock_decision.decision = "ALLOW"
            mock_gate.return_value.check.return_value = mock_decision
            
            with patch('app.services.execution.worker.OrphanPositionGuard') as mock_orphan:
                mock_orphan.return_value.evaluate_and_act.return_value = {
                    "is_orphan": False,
                    "protected": True,
                    "decision": "NOOP",
                    "reason_codes": [],
                    "metadata": {}
                }
                
                with patch('app.services.execution.worker.emit_execution_audit'):
                    with patch('app.services.execution.worker.get_state') as mock_get_state:
                        mock_get_state.return_value = {"global_stop": False, "system_mode": "MANUAL", "airlock_status": "ARMED"}
                        
                        worker.run(max_iterations=1)
    
    # VERIFY: Orphan guard was called at least once
    assert mock_orphan.return_value.evaluate_and_act.call_count >= 1


def test_governance_last_gasp_enforced():
    """Governance last-gasp is enforced before submission"""
    adapter = Mock()
    worker = ExecutionWorker(adapter=adapter, worker_id="test-worker")
    
    with patch('app.services.execution.worker.get_session') as mock_get_session:
        mock_session = Mock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        
        intent = Mock(spec=ExecutionIntent)
        intent.id = "intent_005"
        intent.run_mode = "real"
        
        plan = Mock(spec=OrderPlan)
        plan.id = "plan_005"
        plan.execution_intent_id = "intent_005"
        plan.plan_version = 1
        plan.orders = [{
            "order_index": 0,
            "client_order_id": "test_governance",
            "symbol": "BTC/USDT",
            "side": "BUY",
            "quantity": 0.1,
            "order_type": "ENTRY",
            "order_style": "MARKET"
        }]
        
        mock_session.query.return_value.filter_by.return_value.first.side_effect = [
            intent,
            plan
        ]
        
        # Governance BLOCKS
        with patch('app.services.execution.worker.ExecutionGovernanceGate') as mock_gate:
            mock_decision = Mock()
            mock_decision.decision = "BLOCK"
            mock_decision.reason_codes = ["GLOBAL_STOP_ACTIVE"]
            mock_decision.governance_snapshot = {"global_stop": True}
            mock_gate.return_value.check.return_value = mock_decision
            
            with patch('app.services.execution.worker.emit_execution_audit'):
                try:
                    worker.run(max_iterations=1)
                except:
                    pass  # Expected to raise
    
    # VERIFY: adapter was NEVER called (governance blocked)
    adapter.submit_order.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
