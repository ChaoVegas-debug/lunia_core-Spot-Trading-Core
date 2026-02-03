"""
PHASE 14E — EXECUTION SETTLEMENT: Comprehensive Test Suite

Tests post-trade settlement, ledger persistence, and idempotency.

CRITICAL PROOFS:
- T1: test_not_final_skipped (NEW/PARTIALLY_FILLED → SKIP)
- T2: test_truth_priority_reconciliation_wins (reconciliation > routing)
- T3: test_routing_used_when_no_final_recon (routing fallback)
- T4: test_idempotency_double_call_safe (no double counting)
- T5: test_ledger_first_portfolio_failure (ledger persists)
- T6: test_rejected_terminal_records_ledger_no_portfolio
- T7: test_canceled_terminal_records_ledger_no_portfolio
- T8: test_fail_closed_missing_ids
- T9: test_determinism_byte_for_byte
- T10: test_no_wall_clock_imports_ast
- T11: test_no_trading_static_scan
- T12: test_no_bypass_static_scan

ALL TESTS MOCKED - NO NETWORK
"""

import pytest
import ast
from pathlib import Path
from unittest.mock import Mock

from extensions.execution_settlement.settler import ExecutionSettler
from extensions.execution_settlement.ledger import ExecutionLedger
from extensions.execution_settlement.models import (
    PortfolioApplyResult,
    stable_json,
)


# ────────────────────────────────────────────────────────────────────────────────
# TEST 1: Not Final → Skipped
# ────────────────────────────────────────────────────────────────────────────────

def test_not_final_skipped():
    """
    Prove: routing_result SUCCESS + order_result status NEW/PARTIALLY_FILLED → SKIPPED NOT_FINAL.
    Verify: ledger.record_trade NOT called; portfolio_sink NOT called.
    """
    # Mock ledger
    ledger = Mock()
    ledger.has_processed = Mock(return_value=False)
    ledger.record_trade = Mock()  # Should NEVER be called
    
    # Mock audit store
    audit_store = Mock()
    audit_store.append = Mock(return_value="audit_ref")
    
    # Mock portfolio sink
    portfolio_sink = Mock()
    portfolio_sink.apply_fill = Mock()  # Should NEVER be called
    
    # Create settler
    settler = ExecutionSettler(
        ledger=ledger,
        audit_store=audit_store,
        portfolio_sink=portfolio_sink,
    )
    
    # Create routing_result (SUCCESS with NEW)
    routing_result = {
        "status": "SUCCESS",
        "ts_ms": 1704067200000,
        "decision": {"status": "ALLOWED"},
        "decision_id": "test_decision_new",
        "client_order_id": "BTCUSDT_1704067200000_new123",
        "order_result": {
            "order_id": "999888",
            "client_order_id": "BTCUSDT_1704067200000_new123",
            "symbol": "BTCUSDT",
            "status": "NEW",
            "filled_qty": "0",
            "avg_price": "0",
            "fees": "0",
        },
        "audits": [],
        "error": None,
    }
    
    # Execute
    result_dict = settler.settle(routing_result)
    
    # Verify result
    assert result_dict["status"] == "SKIPPED"
    assert result_dict["skip_reason"] == "NOT_FINAL"
    assert result_dict["terminal_status"] == "NEW"
    
    # Verify ledger NOT called
    ledger.record_trade.assert_not_called()
    
    # Verify portfolio NOT called
    portfolio_sink.apply_fill.assert_not_called()


# ────────────────────────────────────────────────────────────────────────────────
# TEST 2: Truth Priority - Reconciliation Wins
# ────────────────────────────────────────────────────────────────────────────────

def test_truth_priority_reconciliation_wins():
    """
    Prove: routing UNKNOWN + reconciliation FINAL FILLED → use reconciliation.
    Verify: truth_source == "RECONCILIATION", terminal_status == "FILLED".
    """
    # Mock ledger
    ledger = Mock()
    ledger.has_processed = Mock(return_value=False)
    ledger.record_trade = Mock(return_value="ledger_ref_123")
    
    # Mock audit store
    audit_store = Mock()
    audit_store.append = Mock(return_value="audit_ref")
    
    # Mock portfolio sink
    portfolio_sink = Mock()
    portfolio_result = PortfolioApplyResult(updated=True, ref="portfolio_ref_456")
    portfolio_sink.apply_fill = Mock(return_value=portfolio_result)
    
    # Create settler
    settler = ExecutionSettler(
        ledger=ledger,
        audit_store=audit_store,
        portfolio_sink=portfolio_sink,
    )
    
    # Create routing_result (UNKNOWN)
    routing_result = {
        "status": "PARTIAL_FAILURE",
        "ts_ms": 1704067200000,
        "decision": {"status": "ALLOWED"},
        "decision_id": "test_truth_priority",
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
        "error": None,
    }
    
    # Create reconciliation_result (FINAL with FILLED)
    reconciliation_result = {
        "status": "FINAL",
        "ts_ms": 1704067210000,
        "decision_id": "test_truth_priority",
        "client_order_id": "BTCUSDT_1704067200000_xyz789",
        "order_id": "789456",
        "initial": routing_result,
        "reconciled": {
            "order_id": "789456",
            "client_order_id": "BTCUSDT_1704067200000_xyz789",
            "symbol": "BTCUSDT",
            "status": "FILLED",
            "side": "BUY",
            "filled_qty": "0.001",
            "avg_price": "50000",
            "fees": "0.00001",
        },
        "monitor_status": "OK",
        "audits": [],
    }
    
    # Execute
    result_dict = settler.settle(routing_result, reconciliation_result)
    
    # Verify result
    assert result_dict["status"] == "APPLIED"
    assert result_dict["truth_source"] == "RECONCILIATION"
    assert result_dict["terminal_status"] == "FILLED"
    assert result_dict["ledger_ref"] == "ledger_ref_123"
    assert result_dict["portfolio_updated"] is True
    
    # Verify ledger called
    ledger.record_trade.assert_called_once()
    
    # Verify portfolio called
    portfolio_sink.apply_fill.assert_called_once()


# ────────────────────────────────────────────────────────────────────────────────
# TEST 3: Routing Used When No Final Reconciliation
# ────────────────────────────────────────────────────────────────────────────────

def test_routing_used_when_no_final_recon():
    """
    Prove: No reconciliation OR reconciliation not FINAL → use routing.
    Verify: truth_source == "ROUTING".
    """
    # Mock ledger
    ledger = Mock()
    ledger.has_processed = Mock(return_value=False)
    ledger.record_trade = Mock(return_value="ledger_ref_routing")
    
    # Mock audit store
    audit_store = Mock()
    audit_store.append = Mock(return_value="audit_ref")
    
    # Mock portfolio sink
    portfolio_sink = Mock()
    portfolio_result = PortfolioApplyResult(updated=True, ref="portfolio_ref_routing")
    portfolio_sink.apply_fill = Mock(return_value=portfolio_result)
    
    # Create settler
    settler = ExecutionSettler(
        ledger=ledger,
        audit_store=audit_store,
        portfolio_sink=portfolio_sink,
    )
    
    # Create routing_result (SUCCESS with FILLED)
    routing_result = {
        "status": "SUCCESS",
        "ts_ms": 1704067200000,
        "decision": {"status": "ALLOWED"},
        "decision_id": "test_routing_truth",
        "client_order_id": "BTCUSDT_1704067200000_routing456",
        "order_result": {
            "order_id": "123456",
            "client_order_id": "BTCUSDT_1704067200000_routing456",
            "symbol": "BTCUSDT",
            "status": "FILLED",
            "side": "SELL",
            "filled_qty": "0.002",
            "avg_price": "51000",
            "fees": "0.00002",
        },
        "audits": [],
        "error": None,
    }
    
    # No reconciliation (None)
    
    # Execute
    result_dict = settler.settle(routing_result, reconciliation_result=None)
    
    # Verify result
    assert result_dict["status"] == "APPLIED"
    assert result_dict["truth_source"] == "ROUTING"
    assert result_dict["terminal_status"] == "FILLED"
    assert result_dict["ledger_ref"] == "ledger_ref_routing"
    assert result_dict["portfolio_updated"] is True


# ────────────────────────────────────────────────────────────────────────────────
# TEST 4: Idempotency - Double Call Safe
# ────────────────────────────────────────────────────────────────────────────────

def test_idempotency_double_call_safe():
    """
    Prove: settle() twice with same inputs → first APPLIED, second SKIPPED.
    Verify: ledger called once, portfolio called once, second has already_applied=True.
    """
    # Mock audit store
    audit_store = Mock()
    audit_store.append = Mock(return_value="audit_ref")
    
    # Create real ledger (not Mock, to test idempotency logic)
    ledger = ExecutionLedger(audit_store=audit_store, max_index=100)
    
    # Mock portfolio sink
    portfolio_sink = Mock()
    portfolio_result = PortfolioApplyResult(updated=True, ref="portfolio_ref_idem")
    portfolio_sink.apply_fill = Mock(return_value=portfolio_result)
    
    # Create settler
    settler = ExecutionSettler(
        ledger=ledger,
        audit_store=audit_store,
        portfolio_sink=portfolio_sink,
    )
    
    # Create routing_result (FILLED)
    routing_result = {
        "status": "SUCCESS",
        "ts_ms": 1704067200000,
        "decision": {"status": "ALLOWED"},
        "decision_id": "test_idempotency",
        "client_order_id": "BTCUSDT_1704067200000_idem789",
        "order_result": {
            "order_id": "555444",
            "client_order_id": "BTCUSDT_1704067200000_idem789",
            "symbol": "BTCUSDT",
            "status": "FILLED",
            "side": "BUY",
            "filled_qty": "0.001",
            "avg_price": "50000",
            "fees": "0.00001",
        },
        "audits": [],
        "error": None,
    }
    
    # FIRST call
    result1 = settler.settle(routing_result)
    
    # Verify first call
    assert result1["status"] == "APPLIED"
    assert result1["already_applied"] is False
    assert result1["ledger_ref"] is not None
    assert result1["portfolio_updated"] is True
    
    # Verify ledger called once
    assert portfolio_sink.apply_fill.call_count == 1
    
    # SECOND call (identical input)
    result2 = settler.settle(routing_result)
    
    # Verify second call
    assert result2["status"] == "SKIPPED"
    assert result2["skip_reason"] == "ALREADY_APPLIED"
    assert result2["already_applied"] is True
    assert result2["ledger_ref"] is None  # Not appended second time
    assert result2["portfolio_updated"] is False
    
    # Verify portfolio still only called once (no double apply)
    assert portfolio_sink.apply_fill.call_count == 1


# ────────────────────────────────────────────────────────────────────────────────
# TEST 5: Ledger-First Portfolio Failure
# ────────────────────────────────────────────────────────────────────────────────

def test_ledger_first_portfolio_failure():
    """
    Prove: Portfolio exception → ledger still persisted.
    Verify: ledger_ref exists, portfolio_updated=False, status=ERROR.
    """
    # Mock ledger
    ledger = Mock()
    ledger.has_processed = Mock(return_value=False)
    ledger.record_trade = Mock(return_value="ledger_ref_persisted")
    
    # Mock audit store
    audit_store = Mock()
    audit_store.append = Mock(return_value="audit_ref")
    
    # Mock portfolio sink (raises exception)
    portfolio_sink = Mock()
    portfolio_sink.apply_fill = Mock(side_effect=Exception("Portfolio error"))
    
    # Create settler
    settler = ExecutionSettler(
        ledger=ledger,
        audit_store=audit_store,
        portfolio_sink=portfolio_sink,
    )
    
    # Create routing_result (FILLED)
    routing_result = {
        "status": "SUCCESS",
        "ts_ms": 1704067200000,
        "decision": {"status": "ALLOWED"},
        "decision_id": "test_ledger_first",
        "client_order_id": "BTCUSDT_1704067200000_pf_err",
        "order_result": {
            "order_id": "111222",
            "client_order_id": "BTCUSDT_1704067200000_pf_err",
            "symbol": "BTCUSDT",
            "status": "FILLED",
            "side": "BUY",
            "filled_qty": "0.001",
            "avg_price": "50000",
            "fees": "0.00001",
        },
        "audits": [],
        "error": None,
    }
    
    # Execute
    result_dict = settler.settle(routing_result)
    
    # Verify result
    assert result_dict["status"] == "ERROR"
    assert result_dict["ledger_ref"] == "ledger_ref_persisted"  # Ledger persisted!
    assert result_dict["portfolio_updated"] is False
    assert result_dict["error"] is not None
    assert result_dict["error"]["code"] == "SETTLEMENT_003_PORTFOLIO_APPLY_FAILED"
    
    # Verify ledger WAS called (ledger-first)
    ledger.record_trade.assert_called_once()


# ────────────────────────────────────────────────────────────────────────────────
# TEST 6: REJECTED Terminal → Ledger, No Portfolio
# ────────────────────────────────────────────────────────────────────────────────

def test_rejected_terminal_records_ledger_no_portfolio():
    """
    Prove: terminal_status REJECTED → ledger appended, portfolio SKIPPED.
    Verify: ledger_ref exists, portfolio_updated=False.
    """
    # Mock ledger
    ledger = Mock()
    ledger.has_processed = Mock(return_value=False)
    ledger.record_trade = Mock(return_value="ledger_ref_rejected")
    
    # Mock audit store
    audit_store = Mock()
    audit_store.append = Mock(return_value="audit_ref")
    
    # Mock portfolio sink
    portfolio_sink = Mock()
    portfolio_sink.apply_fill = Mock()  # Should NOT be called
    
    # Create settler
    settler = ExecutionSettler(
        ledger=ledger,
        audit_store=audit_store,
        portfolio_sink=portfolio_sink,
    )
    
    # Create routing_result (REJECTED)
    routing_result = {
        "status": "SUCCESS",
        "ts_ms": 1704067200000,
        "decision": {"status": "ALLOWED"},
        "decision_id": "test_rejected",
        "client_order_id": "BTCUSDT_1704067200000_rej123",
        "order_result": {
            "order_id": "333444",
            "client_order_id": "BTCUSDT_1704067200000_rej123",
            "symbol": "BTCUSDT",
            "status": "REJECTED",
            "filled_qty": "0",
            "avg_price": "0",
            "fees": "0",
        },
        "audits": [],
        "error": None,
    }
    
    # Execute
    result_dict = settler.settle(routing_result)
    
    # Verify result
    assert result_dict["status"] == "APPLIED"
    assert result_dict["terminal_status"] == "REJECTED"
    assert result_dict["ledger_ref"] == "ledger_ref_rejected"
    assert result_dict["portfolio_updated"] is False
    
    # Verify ledger called
    ledger.record_trade.assert_called_once()
    
    # Verify portfolio NOT called
    portfolio_sink.apply_fill.assert_not_called()


# ────────────────────────────────────────────────────────────────────────────────
# TEST 7: CANCELED Terminal → Ledger, No Portfolio
# ────────────────────────────────────────────────────────────────────────────────

def test_canceled_terminal_records_ledger_no_portfolio():
    """
    Prove: terminal_status CANCELED → ledger appended, portfolio SKIPPED.
    Verify: ledger_ref exists, portfolio_updated=False.
    """
    # Mock ledger
    ledger = Mock()
    ledger.has_processed = Mock(return_value=False)
    ledger.record_trade = Mock(return_value="ledger_ref_canceled")
    
    # Mock audit store
    audit_store = Mock()
    audit_store.append = Mock(return_value="audit_ref")
    
    # Create settler (no portfolio sink)
    settler = ExecutionSettler(
        ledger=ledger,
        audit_store=audit_store,
        portfolio_sink=None,  # No portfolio
    )
    
    # Create routing_result (CANCELED)
    routing_result = {
        "status": "SUCCESS",
        "ts_ms": 1704067200000,
        "decision": {"status": "ALLOWED"},
        "decision_id": "test_canceled",
        "client_order_id": "BTCUSDT_1704067200000_can456",
        "order_result": {
            "order_id": "666777",
            "client_order_id": "BTCUSDT_1704067200000_can456",
            "symbol": "BTCUSDT",
            "status": "CANCELED",
            "filled_qty": "0",
            "avg_price": "0",
            "fees": "0",
        },
        "audits": [],
        "error": None,
    }
    
    # Execute
    result_dict = settler.settle(routing_result)
    
    # Verify result
    assert result_dict["status"] == "APPLIED"
    assert result_dict["terminal_status"] == "CANCELED"
    assert result_dict["ledger_ref"] == "ledger_ref_canceled"
    assert result_dict["portfolio_updated"] is False
    
    # Verify ledger called
    ledger.record_trade.assert_called_once()


# ────────────────────────────────────────────────────────────────────────────────
# TEST 8: Fail-Closed Missing IDs
# ────────────────────────────────────────────────────────────────────────────────

def test_fail_closed_missing_ids():
    """
    Prove: Missing decision_id → ERROR with no apply.
    Verify: status=ERROR, skip_reason="MISSING_DATA".
    """
    # Mock ledger
    ledger = Mock()
    ledger.has_processed = Mock(return_value=False)
    ledger.record_trade = Mock()  # Should NOT be called
    
    # Mock audit store
    audit_store = Mock()
    audit_store.append = Mock(return_value="audit_ref")
    
    # Create settler
    settler = ExecutionSettler(
        ledger=ledger,
        audit_store=audit_store,
    )
    
    # Create routing_result (missing decision_id)
    routing_result = {
        "status": "SUCCESS",
        "ts_ms": 1704067200000,
        "decision": {"status": "ALLOWED"},  # No id field
        # decision_id: missing!
        "client_order_id": None,
        "order_result": None,
        "audits": [],
        "error": None,
    }
    
    # Execute
    result_dict = settler.settle(routing_result)
    
    # Verify result
    assert result_dict["status"] == "ERROR"
    assert result_dict["skip_reason"] == "MISSING_DATA"
    assert result_dict["error"] is not None
    assert result_dict["error"]["code"] == "SETTLEMENT_001_MISSING_DECISION_ID"
    
    # Verify ledger NOT called
    ledger.record_trade.assert_not_called()


# ────────────────────────────────────────────────────────────────────────────────
# TEST 9: Determinism Byte-for-Byte
# ────────────────────────────────────────────────────────────────────────────────

def test_determinism_byte_for_byte():
    """
    Prove: 10 identical runs → byte-identical stable_json output.
    Verify: len(set(results_json)) == 1.
    """
    # Create deterministic mocks
    audit_store = Mock()
    audit_store.append = Mock(return_value="audit_ref_det")
    
    ledger = Mock()
    ledger.has_processed = Mock(return_value=False)
    ledger.record_trade = Mock(return_value="ledger_ref_det")
    
    portfolio_sink = Mock()
    portfolio_result = PortfolioApplyResult(updated=True, ref="portfolio_ref_det")
    portfolio_sink.apply_fill = Mock(return_value=portfolio_result)
    
    # Create routing_result (deterministic)
    routing_result = {
        "status": "SUCCESS",
        "ts_ms": 1704067200000,
        "decision": {"status": "ALLOWED"},
        "decision_id": "test_determinism",
        "client_order_id": "BTCUSDT_1704067200000_det123",
        "order_result": {
            "order_id": "888999",
            "client_order_id": "BTCUSDT_1704067200000_det123",
            "symbol": "BTCUSDT",
            "status": "FILLED",
            "side": "BUY",
            "filled_qty": "0.001",
            "avg_price": "50000",
            "fees": "0.00001",
        },
        "audits": [],
        "error": None,
    }
    
    # Run 10 times
    results_json = []
    for _ in range(10):
        settler = ExecutionSettler(
            ledger=ledger,
            audit_store=audit_store,
            portfolio_sink=portfolio_sink,
        )
        
        result_dict = settler.settle(routing_result)
        
        # Serialize with stable_json
        result_json = stable_json(result_dict)
        results_json.append(result_json)
    
    # Verify all identical
    assert len(set(results_json)) == 1


# ────────────────────────────────────────────────────────────────────────────────
# TEST 10: No Wall-Clock AST Scan
# ────────────────────────────────────────────────────────────────────────────────

def test_no_wall_clock_imports_ast():
    """
    Prove: No time/datetime/perf_counter imports in settlement.
    Verify: AST scan of models.py, ledger.py, settler.py.
    """
    settlement_files = [
        Path(__file__).parent.parent / "execution_settlement" / "models.py",
        Path(__file__).parent.parent / "execution_settlement" / "ledger.py",
        Path(__file__).parent.parent / "execution_settlement" / "settler.py",
    ]
    
    forbidden_imports = ["time", "datetime"]
    
    for py_file in settlement_files:
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
# TEST 11: No Trading Static Scan
# ────────────────────────────────────────────────────────────────────────────────

def test_no_trading_static_scan():
    """
    Prove: Settlement module has no trading capability.
    Verify: Grep for "create_order", "cancel_order".
    """
    settlement_dir = Path(__file__).parent.parent / "execution_settlement"
    
    if not settlement_dir.exists():
        pytest.skip("Settlement module not found")
    
    forbidden_patterns = [
        "create_order",
        "cancel_order",
        "BinanceExecutionClient(",  # Should not instantiate
    ]
    
    for py_file in settlement_dir.glob("**/*.py"):
        with open(py_file, "r") as f:
            content = f.read()
        
        for pattern in forbidden_patterns:
            assert pattern not in content, \
                f"TRADING DETECTED: {py_file.name} contains '{pattern}'"


# ────────────────────────────────────────────────────────────────────────────────
# TEST 12: No-Bypass Static Scan
# ────────────────────────────────────────────────────────────────────────────────

def test_no_bypass_static_scan():
    """
    Prove: Forbidden modules don't import execution_settlement.
    Verify: Grep scan of shadow_mode/, genome_dsl/, etc.
    """
    forbidden_modules = [
        Path(__file__).parent.parent / "shadow_mode",
        Path(__file__).parent.parent / "genome_dsl",
        Path(__file__).parent.parent / "virtual_portfolio",
        Path(__file__).parent.parent / "hud_api",
        Path(__file__).parent.parent / "execution_gateway",
        Path(__file__).parent.parent / "execution_router",
    ]
    
    forbidden_patterns = [
        "from extensions.execution_settlement import",
        "from .execution_settlement import",
        "from ..execution_settlement import",
        "import execution_settlement",
        "ExecutionSettler",
        "ExecutionLedger",
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
