"""
PHASE 14D — EXECUTION MONITORING: Comprehensive Test Suite

Tests post-trade reconciliation and UNKNOWN status resolution.

CRITICAL PROOFS:
- T1: blocked_path_no_reconcile (BLOCKED → no get_order_status)
- T2: success_final_no_reconcile (FILLED → FINAL)
- T3: unknown_triggers_reconcile_final (UNKNOWN → query → FILLED → FINAL)
- T4: unknown_triggers_reconcile_pending (UNKNOWN → query → NEW → PENDING)
- T5: reconcile_exception_unresolved (UNKNOWN → exception → UNRESOLVED)
- T6: determinism_byte_for_byte (same input → identical JSON)
- T7: no_wall_clock_ast_scan (AST scan for time/datetime)
- T8: no_bypass_static_scan (verify forbidden dirs clean)

ALL TESTS MOCKED - NO NETWORK
"""

import pytest
import ast
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

from extensions.execution_monitoring.monitor import ExecutionMonitor
from extensions.execution_monitoring.models import stable_json
from extensions.exchange_connectivity.trade_models import OrderResult


# ────────────────────────────────────────────────────────────────────────────────
# TEST 1: Blocked Path (No Reconciliation)
# ────────────────────────────────────────────────────────────────────────────────

def test_blocked_path_no_reconcile():
    """
    Prove: routing_result BLOCKED → get_order_status NOT called.
    Verify: ReconciliationStatus FINAL, reconciled=None.
    Verify: Exactly 2 audits (M1, M3).
    """
    # Mock client
    client = Mock()
    client.get_order_status = Mock()  # Should NEVER be called
    
    # Mock audit store
    audit_store = Mock()
    audit_store.append = Mock(return_value="audit_ref")
    
    # Create monitor
    monitor = ExecutionMonitor(
        client=client,
        audit_store=audit_store,
    )
    
    # Create routing_result (BLOCKED)
    routing_result = {
        "status": "BLOCKED",
        "ts_ms": 1704067200000,
        "decision": {"status": "BLOCKED", "reason_code": "KS_001"},
        "decision_id": "test_decision_123",
        "client_order_id": None,
        "order_result": None,
        "audits": [],
        "error": None,
    }
    
    # Execute
    recon_dict = monitor.reconcile(routing_result)
    
    # Verify result
    assert recon_dict["status"] == "FINAL"
    assert recon_dict["reconciled"] is None
    assert recon_dict["monitor_status"] == "OK"
    
    # Verify client NOT called
    client.get_order_status.assert_not_called()
    
    # Verify exactly 2 audits (M1, M3)
    assert audit_store.append.call_count == 2
    
    # Verify audit events
    audits = recon_dict["audits"]
    assert len(audits) == 2
    assert audits[0]["event"] == "MONITOR_INPUT"
    assert audits[1]["event"] == "MONITOR_SUMMARY"


# ──────────────────────────────────────────────────────────────────────────────── 
# TEST 2: Success Final (No Reconciliation)
# ────────────────────────────────────────────────────────────────────────────────

def test_success_final_no_reconcile():
    """
    Prove: routing_result SUCCESS + order FILLED → no reconciliation.
    Verify: ReconciliationStatus FINAL, get_order_status NOT called.
    Verify: Exactly 2 audits (M1, M3).
    """
    # Mock client
    client = Mock()
    client.get_order_status = Mock()  # Should NEVER be called
    
    # Mock audit store
    audit_store = Mock()
    audit_store.append = Mock(return_value="audit_ref")
    
    # Create monitor
    monitor = ExecutionMonitor(
        client=client,
        audit_store=audit_store,
    )
    
    # Create routing_result (SUCCESS with FILLED)
    routing_result = {
        "status": "SUCCESS",
        "ts_ms": 1704067200000,
        "decision": {"status": "ALLOWED"},
        "decision_id": "test_decision_456",
        "client_order_id": "BTCUSDT_1704067200000_abc123",
        "order_result": {
            "order_id": "123456",
            "client_order_id": "BTCUSDT_1704067200000_abc123",
            "symbol": "BTCUSDT",
            "status": "FILLED",
            "filled_qty": "0.001",
            "avg_price": "50000",
            "fees": "0.00001",
        },
        "audits": [],
        "error": None,
    }
    
    # Execute
    recon_dict = monitor.reconcile(routing_result)
    
    # Verify result
    assert recon_dict["status"] == "FINAL"
    assert recon_dict["reconciled"] is None  # No reconciliation needed
    assert recon_dict["monitor_status"] == "OK"
    
    # Verify client NOT called
    client.get_order_status.assert_not_called()
    
    # Verify exactly 2 audits (M1, M3)
    assert audit_store.append.call_count == 2


# ────────────────────────────────────────────────────────────────────────────────
# TEST 3: UNKNOWN Triggers Reconcile → FINAL
# ────────────────────────────────────────────────────────────────────────────────

def test_unknown_triggers_reconcile_final():
    """
    Prove: initial UNKNOWN → get_order_status called → returns FILLED.
    Verify: ReconciliationStatus FINAL, reconciled present.
    Verify: 3 audits (M1, M2, M3).
    """
    # Mock client (returns FILLED)
    client = Mock()
    reconciled_order = OrderResult(
        order_id="789456",
        client_order_id="BTCUSDT_1704067200000_xyz789",
        symbol="BTCUSDT",
        status="FILLED",
        filled_qty=Decimal("0.001"),
        avg_price=Decimal("50000"),
        fees=Decimal("0.00001"),
    )
    client.get_order_status = Mock(return_value=reconciled_order)
    
    # Mock audit store
    audit_store = Mock()
    audit_store.append = Mock(return_value="audit_ref")
    
    # Create monitor
    monitor = ExecutionMonitor(
        client=client,
        audit_store=audit_store,
    )
    
    # Create routing_result (STATUS with UNKNOWN)
    routing_result = {
        "status": "PARTIAL_FAILURE",
        "ts_ms": 1704067200000,
        "decision": {"status": "ALLOWED"},
        "decision_id": "test_decision_789",
        "client_order_id": "BTCUSDT_1704067200000_xyz789",
        "order_result": {
            "order_id": None,
            "client_order_id": "BTCUSDT_1704067200000_xyz789",
            "symbol": "BTCUSDT",
            "status": "UNKNOWN",
            "filled_qty": "0",
            "avg_price": "0",
            "fees": "0",
        },
        "audits": [],
        "error": {"code": "ROUTER_004_CLIENT_EXCEPTION"},
    }
    
    # Execute
    recon_dict = monitor.reconcile(routing_result)
    
    # Verify result
    assert recon_dict["status"] == "FINAL"
    assert recon_dict["reconciled"] is not None
    assert recon_dict["reconciled"]["status"] == "FILLED"
    assert recon_dict["monitor_status"] == "OK"
    
    # Verify client WAS called
    client.get_order_status.assert_called_once()
    call_kwargs = client.get_order_status.call_args[1]
    assert call_kwargs["symbol"] == "BTCUSDT"
    assert call_kwargs["client_order_id"] == "BTCUSDT_1704067200000_xyz789"
    
    # Verify exactly 3 audits (M1, M2, M3)
    assert audit_store.append.call_count == 3
    
    # Verify audit events
    audits = recon_dict["audits"]
    assert len(audits) == 3
    assert audits[0]["event"] == "MONITOR_INPUT"
    assert audits[1]["event"] == "MONITOR_RECONCILE_RESULT"
    assert audits[2]["event"] == "MONITOR_SUMMARY"


# ────────────────────────────────────────────────────────────────────────────────
# TEST 4: UNKNOWN Triggers Reconcile → PENDING
# ────────────────────────────────────────────────────────────────────────────────

def test_unknown_triggers_reconcile_pending():
    """
    Prove: initial UNKNOWN → get_order_status returns NEW/PARTIALLY_FILLED.
    Verify: ReconciliationStatus PENDING (active order).
    Verify: 3 audits (M1, M2, M3).
    """
    # Mock client (returns NEW)
    client = Mock()
    reconciled_order = OrderResult(
        order_id="999888",
        client_order_id="BTCUSDT_1704067200000_pqr456",
        symbol="BTCUSDT",
        status="NEW",
        filled_qty=Decimal("0"),
        avg_price=Decimal("0"),
        fees=Decimal("0"),
    )
    client.get_order_status = Mock(return_value=reconciled_order)
    
    # Mock audit store
    audit_store = Mock()
    audit_store.append = Mock(return_value="audit_ref")
    
    # Create monitor
    monitor = ExecutionMonitor(
        client=client,
        audit_store=audit_store,
    )
    
    # Create routing_result (UNKNOWN)
    routing_result = {
        "status": "PARTIAL_FAILURE",
        "ts_ms": 1704067200000,
        "decision": {"status": "ALLOWED"},
        "decision_id": "test_decision_pending",
        "client_order_id": "BTCUSDT_1704067200000_pqr456",
        "order_result": {
            "order_id": None,
            "client_order_id": "BTCUSDT_1704067200000_pqr456",
            "symbol": "BTCUSDT",
            "status": "UNKNOWN",
            "filled_qty": "0",
            "avg_price": "0",
            "fees": "0",
        },
        "audits": [],
        "error": None,
    }
    
    # Execute
    recon_dict = monitor.reconcile(routing_result)
    
    # Verify result
    assert recon_dict["status"] == "PENDING"
    assert recon_dict["reconciled"] is not None
    assert recon_dict["reconciled"]["status"] == "NEW"
    assert recon_dict["monitor_status"] == "OK"
    
    # Verify 3 audits
    assert audit_store.append.call_count == 3


# ────────────────────────────────────────────────────────────────────────────────
# TEST 5: Reconcile Exception → UNRESOLVED
# ────────────────────────────────────────────────────────────────────────────────

def test_reconcile_exception_unresolved():
    """
    Prove: initial UNKNOWN → get_order_status raises → UNRESOLVED.
    Verify: ReconciliationStatus UNRESOLVED, error present.
    Verify: 3 audits (M1, M2, M3).
    """
    # Mock client (raises exception)
    client = Mock()
    client.get_order_status = Mock(side_effect=Exception("Connection timeout"))
    
    # Mock audit store
    audit_store = Mock()
    audit_store.append = Mock(return_value="audit_ref")
    
    # Create monitor
    monitor = ExecutionMonitor(
        client=client,
        audit_store=audit_store,
    )
    
    # Create routing_result (UNKNOWN)
    routing_result = {
        "status": "PARTIAL_FAILURE",
        "ts_ms": 1704067200000,
        "decision": {"status": "ALLOWED"},
        "decision_id": "test_decision_error",
        "client_order_id": "BTCUSDT_1704067200000_err999",
        "order_result": {
            "order_id": None,
            "client_order_id": "BTCUSDT_1704067200000_err999",
            "symbol": "BTCUSDT",
            "status": "UNKNOWN",
            "filled_qty": "0",
            "avg_price": "0",
            "fees": "0",
        },
        "audits": [],
        "error": None,
    }
    
    # Execute
    recon_dict = monitor.reconcile(routing_result)
    
    # Verify result
    assert recon_dict["status"] == "UNRESOLVED"
    assert recon_dict["reconciled"] is None
    assert recon_dict["monitor_status"] == "ERROR"
    assert recon_dict["error"] is not None
    assert recon_dict["error"]["code"] == "MONITOR_003_RECONCILE_FAILED"
    
    # Verify 3 audits (M1, M2 with error, M3)
    assert audit_store.append.call_count == 3


# ────────────────────────────────────────────────────────────────────────────────
# TEST 6: Determinism Byte-for-Byte
# ────────────────────────────────────────────────────────────────────────────────

def test_determinism_byte_for_byte():
    """
    Prove: Same mocked inputs → byte-identical stable_json(ReconciliationResult).
    Verify: 10 identical runs → identical JSON bytes.
    """
    # Create deterministic mocks
    client = Mock()
    reconciled_order = OrderResult(
        order_id="deterministic_123",
        client_order_id="BTCUSDT_1704067200000_det456",
        symbol="BTCUSDT",
        status="FILLED",
        filled_qty=Decimal("0.001"),
        avg_price=Decimal("50000"),
        fees=Decimal("0.00001"),
    )
    client.get_order_status = Mock(return_value=reconciled_order)
    
    audit_store = Mock()
    audit_store.append = Mock(return_value="audit_ref")
    
    # Create routing_result (deterministic)
    routing_result = {
        "status": "PARTIAL_FAILURE",
        "ts_ms": 1704067200000,
        "decision": {"status": "ALLOWED"},
        "decision_id": "test_determinism",
        "client_order_id": "BTCUSDT_1704067200000_det456",
        "order_result": {
            "order_id": None,
            "client_order_id": "BTCUSDT_1704067200000_det456",
            "symbol": "BTCUSDT",
            "status": "UNKNOWN",
            "filled_qty": "0",
            "avg_price": "0",
            "fees": "0",
        },
        "audits": [],
        "error": None,
    }
    
    # Run 10 times
    results_json = []
    for _ in range(10):
        monitor = ExecutionMonitor(
            client=client,
            audit_store=audit_store,
        )
        
        recon_dict = monitor.reconcile(routing_result)
        
        # Serialize with stable_json
        result_json = stable_json(recon_dict)
        results_json.append(result_json)
    
    # Verify all identical
    assert len(set(results_json)) == 1


# ────────────────────────────────────────────────────────────────────────────────
# TEST 7: No Wall-Clock AST Scan
# ────────────────────────────────────────────────────────────────────────────────

def test_no_wall_clock_imports_ast():
    """
    Prove: No time/datetime/perf_counter imports in monitoring.
    Verify: AST scan of monitor.py and models.py.
    """
    monitor_files = [
        Path(__file__).parent.parent / "execution_monitoring" / "monitor.py",
        Path(__file__).parent.parent / "execution_monitoring" / "models.py",
    ]
    
    forbidden_imports = ["time", "datetime"]
    
    for py_file in monitor_files:
        if not py_file.exists():
            continue
        
        with open(py_file, "r") as f:
            source = f.read()
        
        tree = ast.parse(source, filename=str(py_file))
        
        # Check imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name not in forbidden_imports, \
                        f"{py_file.name}: Forbidden import: {alias.name}"
            
            elif isinstance(node, ast.ImportFrom):
                if node.module in forbidden_imports:
                    assert False, f"{py_file.name}: Forbidden import from: {node.module}"


# ────────────────────────────────────────────────────────────────────────────────
# TEST 8: No-Bypass Static Scan
# ────────────────────────────────────────────────────────────────────────────────

def test_no_bypass_static_scan():
    """
    Prove: Forbidden modules don't import execution_monitoring.
    Verify: Grep scan of shadow_mode/, genome_dsl/, etc.
    """
    forbidden_modules = [
        Path(__file__).parent.parent / "shadow_mode",
        Path(__file__).parent.parent / "genome_dsl",
        Path(__file__).parent.parent / "virtual_portfolio",
        Path(__file__).parent.parent / "hud_api",
        Path(__file__).parent.parent / "execution_gateway",
    ]
    
    forbidden_patterns = [
        "from extensions.execution_monitoring import",
        "from .execution_monitoring import",
        "from ..execution_monitoring import",
        "import execution_monitoring",
        "ExecutionMonitor",
    ]
    
    for module_dir in forbidden_modules:
        if not module_dir.exists():
            continue
        
        for py_file in module_dir.glob("**/*.py"):
            with open(py_file, "r") as f:
                content = f.read()
            
            for pattern in forbidden_patterns:
                assert pattern not in content, \
                    f"BYPASS DETECTED: {py_file.relative_to(module_dir.parent)} contains '{pattern}'"
