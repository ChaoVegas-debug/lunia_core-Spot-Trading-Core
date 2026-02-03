"""
PHASE 14C — EXECUTION ROUTER: Comprehensive Test Suite

Tests the single chokepoint (gateway → router → client).

CRITICAL PROOFS:
- T1: Flow Success (gateway ALLOWED → client called → 3 audits)
- T2: Blocked (gateway BLOCKED → client NOT called)
- T3: Double Kill Switch (ALLOWED + kill switch → client NOT called)
- T4: Client Exception → UNKNOWN (fail-safe)
- T5: Determinism Byte-for-Byte
- T6: No Wall-Clock AST Scan
- T7: No-Bypass Static Scan

ALL TESTS MOCKED - NO NETWORK
"""

import pytest
import ast
import hashlib
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from extensions.execution_router.router import ExecutionRouter
from extensions.execution_router.models import stable_json, derive_decision_id
from extensions.execution_gateway.models import (
    ExecutionRequest,
    ExecutionContextSnapshot,
    ExecutionDecision,
    AuditPayload,
    RiskLimits,
)
from extensions.execution_gateway.airlock import ExecutionGateway
from extensions.exchange_connectivity.trade_models import OrderResult
from extensions.genome_dsl.audit_store import AuditStore


# ────────────────────────────────────────────────────────────────────────────────
# TEST 1: Flow Success
# ────────────────────────────────────────────────────────────────────────────────

def test_flow_success():
    """
    Prove: Gateway ALLOWED → client called → SUCCESS result.
    Verify: 3 audits appended (A: gateway, B: router, C: execution).
    Verify: decision_id ↔ client_order_id ↔ order_id binding.
    """
    # Mock gateway
    gateway = Mock()
    gateway._kill_switch = Mock(enabled=False)
    
    decision = ExecutionDecision(
        status="ALLOWED",
        reason_code="OK",
        reason_message="All checks passed",
        checks_passed={"KS_001": True, "ARM_002": True},
        ts_ms=1704067200000,
        normalized_symbol="BTCUSDT",
    )
    
    audit_payload = AuditPayload(
        schema_version="1.0.0",
        phase="14A",
        event="EXECUTION_GATEWAY_EVALUATED",
        timestamp_ms=1704067200000,
        symbol="BTCUSDT",
        data={
            "decision": decision.to_dict(),
            "context_digest": "test_digest_123",
        },
    )
    
    gateway.evaluate = Mock(return_value=(decision, audit_payload))
    
    # Mock client
    client = Mock()
    order_result = OrderResult(
        order_id="123456",
        client_order_id="BTCUSDT_1704067200000_abcd1234",
        symbol="BTCUSDT",
        status="FILLED",
        filled_qty=Decimal("0.001"),
        avg_price=Decimal("50000"),
        fees=Decimal("0.00001"),
    )
    client.create_order = Mock(return_value=order_result)
    
    # Mock audit store
    audit_store = Mock()
    audit_store.append = Mock(return_value="audit_ref")
    
    # Create router
    router = ExecutionRouter(
        gateway=gateway,
        client=client,
        audit_store=audit_store,
        test_mode=True,
    )
    
    # Create request
    request = ExecutionRequest(
        intent={
            "signal": "BUY",
            "virtual_order": {
                "side": "BUY",
                "fill_price": "50000",
                "quantity": "0.001",
                "price_type": "IMMEDIATE_FILL",
            },
        },
        symbol="BTCUSDT",
        ts_ms=1704067200000,
    )
    
    context = ExecutionContextSnapshot(
        snapshot={"symbol": "BTCUSDT", "health": {"is_fresh": True, "is_synced": True}},
        portfolio_state={"equity": "10000"},
        system_health={"supervisor": {"status": "OK"}},
        ts_ms=1704067200000,
    )
    
    # Execute
    result_dict = router.route(request, context=context)
    
    # Verify result
    assert result_dict["status"] == "SUCCESS"
    assert result_dict["decision_id"] == "test_digest_123"
    assert result_dict["client_order_id"] == "BTCUSDT_1704067200000_abcd1234"
    assert result_dict["order_result"]["order_id"] == "123456"
    assert result_dict["order_result"]["status"] == "FILLED"
    
    # Verify client was called exactly once
    client.create_order.assert_called_once()
    call_kwargs = client.create_order.call_args[1]
    assert call_kwargs["symbol"] == "BTCUSDT"
    assert call_kwargs["side"] == "BUY"
    assert call_kwargs["quantity"] == Decimal("0.001")
    assert call_kwargs["test_mode"] is True
    
    # Verify 3 audits appended (A, B, C)
    assert audit_store.append.call_count >= 3
    
    # Verify decision_id binding in audits
    assert len(result_dict["audits"]) >= 3
    
    # Check execution audit for binding
    execution_audit = None
    for audit in result_dict["audits"]:
        if audit.get("event") == "EXECUTION_RESULT":
            execution_audit = audit
            break
    
    assert execution_audit is not None
    assert execution_audit["data"]["decision_id"] == "test_digest_123"
    assert execution_audit["data"]["client_order_id"] == "BTCUSDT_1704067200000_abcd1234"
    assert execution_audit["data"]["order_id"] == "123456"


# ────────────────────────────────────────────────────────────────────────────────
# TEST 2: Blocked Path
# ────────────────────────────────────────────────────────────────────────────────

def test_blocked_path():
    """
    Prove: Gateway BLOCKED → client NEVER called.
    Verify: 2 audits appended (A: gateway, B: router).
    Verify: RoutingResult status = BLOCKED.
    """
    # Mock gateway (returns BLOCKED)
    gateway = Mock()
    
    decision = ExecutionDecision(
        status="BLOCKED",
        reason_code="KS_001",
        reason_message="Kill switch enabled",
        checks_passed={"KS_001": False},
        ts_ms=1704067200000,
        normalized_symbol="BTCUSDT",
    )
    
    audit_payload = AuditPayload(
        schema_version="1.0.0",
        phase="14A",
        event="EXECUTION_GATEWAY_EVALUATED",
        timestamp_ms=1704067200000,
        symbol="BTCUSDT",
        data={
            "decision": decision.to_dict(),
            "context_digest": "blocked_digest",
        },
    )
    
    gateway.evaluate = Mock(return_value=(decision, audit_payload))
    
    # Mock client
    client = Mock()
    client.create_order = Mock()  # Should NEVER be called
    
    # Mock audit store
    audit_store = Mock()
    audit_store.append = Mock(return_value="audit_ref")
    
    # Create router
    router = ExecutionRouter(
        gateway=gateway,
        client=client,
        audit_store=audit_store,
    )
    
    # Create request
    request = ExecutionRequest(
        intent={"signal": "BUY", "virtual_order": {"side": "BUY", "fill_price": "50000"}},
        symbol="BTCUSDT",
        ts_ms=1704067200000,
    )
    
    context = ExecutionContextSnapshot(
        snapshot=None,
        portfolio_state=None,
        system_health=None,
    )
    
    # Execute
    result_dict = router.route(request, context=context)
    
    # Verify result
    assert result_dict["status"] == "BLOCKED"
    assert result_dict["decision"]["status"] == "BLOCKED"
    assert result_dict["decision"]["reason_code"] == "KS_001"
    assert result_dict["client_order_id"] is None
    assert result_dict["order_result"] is None
    
    # Verify client was NEVER called
    client.create_order.assert_not_called()
    
    # Verify at least 2 audits appended (gateway + router)
    assert audit_store.append.call_count >= 2
    
    # Verify audits
    assert len(result_dict["audits"]) >= 2
    
    # Check router audit
    router_audit = None
    for audit in result_dict["audits"]:
        if audit.get("event") == "ROUTER_ROUTE_RESULT":
            router_audit = audit
            break
    
    assert router_audit is not None
    assert router_audit["data"]["status"] == "BLOCKED"


# ────────────────────────────────────────────────────────────────────────────────
# TEST 3: Double Kill Switch
# ────────────────────────────────────────────────────────────────────────────────

def test_double_kill_switch():
    """
    Prove: Gateway ALLOWED + kill switch enabled at second gate → client NOT called.
    Verify: Defense-in-depth working.
    Verify: Status BLOCKED with code "KILL_SWITCH_RERAISED".
    """
    # Mock gateway (returns ALLOWED but kill switch becomes enabled)
    gateway = Mock()
    
    decision = ExecutionDecision(
        status="ALLOWED",
        reason_code="OK",
        reason_message="All checks passed",
        checks_passed={"KS_001": True, "ARM_002": True},
        ts_ms=1704067200000,
        normalized_symbol="BTCUSDT",
    )
    
    audit_payload = AuditPayload(
        schema_version="1.0.0",
        phase="14A",
        event="EXECUTION_GATEWAY_EVALUATED",
        timestamp_ms=1704067200000,
        symbol="BTCUSDT",
        data={
            "decision": decision.to_dict(),
            "context_digest": "ks_test",
        },
    )
    
    gateway.evaluate = Mock(return_value=(decision, audit_payload))
    
    # Kill switch enabled at second gate (defense-in-depth)
    gateway._kill_switch = Mock(enabled=True, reason="Emergency stop")
    
    # Mock client
    client = Mock()
    client.create_order = Mock()  # Should NEVER be called
    
    # Mock audit store
    audit_store = Mock()
    audit_store.append = Mock(return_value="audit_ref")
    
    # Create router
    router = ExecutionRouter(
        gateway=gateway,
        client=client,
        audit_store=audit_store,
    )
    
    # Create request
    request = ExecutionRequest(
        intent={"signal": "BUY", "virtual_order": {"side": "BUY", "fill_price": "50000"}},
        symbol="BTCUSDT",
        ts_ms=1704067200000,
    )
    
    context = ExecutionContextSnapshot(
        snapshot=None,
        portfolio_state=None,
        system_health=None,
    )
    
    # Execute
    result_dict = router.route(request, context=context)
    
    # Verify result
    assert result_dict["status"] == "BLOCKED"
    assert result_dict["client_order_id"] is None
    
    # Verify client was NEVER called
    client.create_order.assert_not_called()
    
    # Verify router audit contains "KILL_SWITCH_RERAISED"
    router_audit = None
    for audit in result_dict["audits"]:
        if audit.get("event") == "ROUTER_ROUTE_RESULT":
            router_audit = audit
            break
    
    assert router_audit is not None
    assert router_audit["data"]["reason_code"] == "KILL_SWITCH_RERAISED"
    assert router_audit["data"].get("defense_in_depth") is True


# ────────────────────────────────────────────────────────────────────────────────
# TEST 4: Client Exception → UNKNOWN
# ────────────────────────────────────────────────────────────────────────────────

def test_client_exception_unknown():
    """
    Prove: Client raises exception → fail-safe PARTIAL_FAILURE result.
    Verify: RoutingResult status = PARTIAL_FAILURE.
    Verify: Audits still written (A, B, C).
    """
    # Mock gateway
    gateway = Mock()
    gateway._kill_switch = Mock(enabled=False)
    
    decision = ExecutionDecision(
        status="ALLOWED",
        reason_code="OK",
        reason_message="All checks passed",
        checks_passed={"KS_001": True},
        ts_ms=1704067200000,
        normalized_symbol="BTCUSDT",
    )
    
    audit_payload = AuditPayload(
        schema_version="1.0.0",
        phase="14A",
        event="EXECUTION_GATEWAY_EVALUATED",
        timestamp_ms=1704067200000,
        symbol="BTCUSDT",
        data={
            "decision": decision.to_dict(),
            "context_digest": "err_test",
        },
    )
    
    gateway.evaluate = Mock(return_value=(decision, audit_payload))
    
    # Mock client (raises exception)
    client = Mock()
    client.create_order = Mock(side_effect=Exception("Connection timeout"))
    
    # Mock audit store
    audit_store = Mock()
    audit_store.append = Mock(return_value="audit_ref")
    
    # Create router
    router = ExecutionRouter(
        gateway=gateway,
        client=client,
        audit_store=audit_store,
    )
    
    # Create request
    request = ExecutionRequest(
        intent={"signal": "BUY", "virtual_order": {"side": "BUY", "fill_price": "50000"}},
        symbol="BTCUSDT",
        ts_ms=1704067200000,
    )
    
    context = ExecutionContextSnapshot(
        snapshot=None,
        portfolio_state=None,
        system_health=None,
    )
    
    # Execute
    result_dict = router.route(request, context=context)
    
    # Verify result
    assert result_dict["status"] == "PARTIAL_FAILURE"
    assert result_dict["error"] is not None
    assert result_dict["error"]["code"] == "ROUTER_004_CLIENT_EXCEPTION"
    assert result_dict["order_result"]["status"] == "UNKNOWN"
    
    # Verify audits still written (A, B, C)
    assert audit_store.append.call_count >= 3


# ────────────────────────────────────────────────────────────────────────────────
# TEST 5: Determinism Byte-for-Byte
# ────────────────────────────────────────────────────────────────────────────────

def test_determinism_byte_for_byte():
    """
    Prove: Same mocked inputs → byte-identical stable_json(RoutingResult).
    Verify: 10 identical runs → identical JSON bytes.
    """
    # Create deterministic mocks
    gateway = Mock()
    gateway._kill_switch = Mock(enabled=False)
    
    decision = ExecutionDecision(
        status="ALLOWED",
        reason_code="OK",
        reason_message="All checks passed",
        checks_passed={"KS_001": True},
        ts_ms=1704067200000,
        normalized_symbol="BTCUSDT",
    )
    
    audit_payload = AuditPayload(
        schema_version="1.0.0",
        phase="14A",
        event="EXECUTION_GATEWAY_EVALUATED",
        timestamp_ms=1704067200000,
        symbol="BTCUSDT",
        data={
            "decision": decision.to_dict(),
            "context_digest": "determ_test",
        },
    )
    
    gateway.evaluate = Mock(return_value=(decision, audit_payload))
    
    # Mock client (deterministic response)
    client = Mock()
    order_result = OrderResult(
        order_id="123456",
        client_order_id="BTCUSDT_1704067200000_12345678",
        symbol="BTCUSDT",
        status="FILLED",
        filled_qty=Decimal("0.001"),
        avg_price=Decimal("50000"),
        fees=Decimal("0.00001"),
    )
    client.create_order = Mock(return_value=order_result)
    
    # Mock audit store
    audit_store = Mock()
    audit_store.append = Mock(return_value="audit_ref")
    
    # Run 10 times
    results_json = []
    for _ in range(10):
        router = ExecutionRouter(
            gateway=gateway,
            client=client,
            audit_store=audit_store,
        )
        
        request = ExecutionRequest(
            intent={"signal": "BUY", "virtual_order": {"side": "BUY", "fill_price": "50000"}},
            symbol="BTCUSDT",
            ts_ms=1704067200000,
        )
        
        context = ExecutionContextSnapshot(
            snapshot=None,
            portfolio_state=None,
            system_health=None,
        )
        
        result_dict = router.route(request, context=context)
        
        # Serialize with stable_json
        result_json = stable_json(result_dict)
        results_json.append(result_json)
    
    # Verify all identical
    assert len(set(results_json)) == 1


# ────────────────────────────────────────────────────────────────────────────────
# TEST 6: No Wall-Clock AST Scan
# ────────────────────────────────────────────────────────────────────────────────

def test_no_wall_clock_imports_ast():
    """
    Prove: No time/datetime/perf_counter imports in router.
    Verify: AST scan of router.py and models.py.
    """
    router_files = [
        Path(__file__).parent.parent / "execution_router" / "router.py",
        Path(__file__).parent.parent / "execution_router" / "models.py",
    ]
    
    forbidden_imports = ["time", "datetime"]
    
    for py_file in router_files:
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
# TEST 7: No-Bypass Static Scan
# ────────────────────────────────────────────────────────────────────────────────

def test_no_bypass_static_scan():
    """
    Prove: Only execution_router/* and tests import execution_client.
    Verify: Grep scan of forbidden modules shows zero matches.
    Verify: Single chokepoint enforcement.
    """
    forbidden_modules = [
        Path(__file__).parent.parent / "shadow_mode",
        Path(__file__).parent.parent / "genome_dsl",
        Path(__file__).parent.parent / "virtual_portfolio",
        Path(__file__).parent.parent / "hud_api",
        Path(__file__).parent.parent / "execution_gateway",
    ]
    
    forbidden_patterns = [
        "from extensions.exchange_connectivity.execution_client import",
        "from .exchange_connectivity.execution_client import",
        "from ..exchange_connectivity.execution_client import",
        "import execution_client",
        "BinanceExecutionClient",
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
