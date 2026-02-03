"""
PHASE 13A — SHADOW RUNNER: Tests

Comprehensive test suite for shadow execution.

All tests use mocks (no real network).
"""

import pytest
import json
import ast
from pathlib import Path
from unittest.mock import MagicMock, patch
from extensions.shadow_mode import models, adapter, loop, supervisor
from extensions.genome_dsl.audit_store import MemoryAuditStore


# ────────────────────────────────────────────────────────────────────────────────
# FIXTURES
# ────────────────────────────────────────────────────────────────────────────────

def create_mock_pump(snapshot_override=None):
    """Create mock LiveDataPump."""
    mock_pump = MagicMock()
    mock_pump.tick.return_value = {"ok": True}
    mock_pump.get_latest_snapshot.return_value = snapshot_override
    return mock_pump


def create_fresh_snapshot():
    """Create fresh market snapshot."""
    return {
        "ok": True,
        "symbol": "BTCUSDT",
        "event_ts_ms": 1737900000000,
        "server_ts_ms": 1737900000000,
        "source": {"exchange": "binance", "mode": "rest_fallback", "streams": None},
        "book": {
            "depth": 20,
            "bids": [["50000.00", "1.0"]],
            "asks": [["50100.00", "1.5"]],
            "last_update_id": 12345,
        },
        "top": {
            "best_bid": "50000.00",
            "best_ask": "50100.00",
            "mid": "50050.00",
            "spread": "100.00",
        },
        "trade": {"price": "50050.00", "qty": "1.0", "trade_ts_ms": 1737900000000},
        "health": {
            "is_synced": True,
            "is_fresh": True,
            "stale_reason": None,
            "last_error": None,
        },
    }


def create_stale_snapshot():
    """Create stale market snapshot."""
    snap = create_fresh_snapshot()
    snap["health"]["is_fresh"] = False
    snap["health"]["stale_reason"] = "NO_EVENTS"
    return snap


def create_entry_genome():
    """Create minimal genome that yields ENTRY intent."""
    return {
        "__type__": "StrategyGenome",
        "metadata": {"strategy_id": "test_strategy", "name": "Test Strategy", "symbol": "BTCUSDT"},
        "entry_conditions": {
            "__type__": "Composite",
            "op": "AND",
            "inputs": [],
            "metadata": {},
        },
        "sizing": {
            "__type__": "Constant",
            "value": 0.1,
            "metadata": {},
        },
        "exit_plan": {
            "__type__": "ExitPlan",
            "stop_loss_pct": 0.02,
            "take_profit_pct": 0.05,
            "time_limit_ms": 3600000,
            "metadata": {},
        },
    }


# ────────────────────────────────────────────────────────────────────────────────
# T1: END-TO-END FLOW (FIRST SPARK)
# ────────────────────────────────────────────────────────────────────────────────

def test_end_to_end_first_spark():
    """Test complete flow: Pump → Snapshot → execute_genome → Adapter → Audit."""
    # Setup
    snapshot = create_fresh_snapshot()
    mock_pump = create_mock_pump(snapshot)
    genome_json = create_entry_genome()
    context_template = {"governance_level": "AUTO"}
    audit_store = MemoryAuditStore()
    
    # Mock execute_genome to return ENTRY intent
    with patch("extensions.shadow_mode.loop.execute_genome") as mock_exec:
        mock_exec.return_value = {
            "decision_evidence": {},
            "strategy_intent": {
                "intent_id": "test_intent_123",
                "ts_ms": 1737900000000,
                "intent_type": "ENTRY",
                "direction": "LONG",
                "confidence": 0.85,
                "rationale": "Strong uptrend detected",
            },
            "proposal_card": {},
            "audit_ref": "genome_audit_123",
            "hashes": {},
            "evidence_bundle": {},
        }
        
        # Create loop
        shadow_loop = loop.ShadowLoop(
            pump=mock_pump,
            genome_json=genome_json,
            context_template=context_template,
            audit_store=audit_store,
            symbol="BTCUSDT",
        )
        
        # Tick
        result = shadow_loop.tick(snapshot_override=snapshot)
        
        # Assertions
        assert result.status == "EXECUTED"
        assert result.decision_id == "test_intent_123"
        assert result.intent is not None
        assert result.intent.signal == "ENTRY_BUY"
        assert result.virtual_order is not None
        assert result.virtual_order.side == "BUY"
        assert result.virtual_order.fill_price == "50100.00"  # BUY at ask
        assert result.audit_ref != ""
        assert result.audit_ref != "AUDIT_WRITE_FAILED"
        
        # Verify audit record was persisted
        assert len(audit_store.records) >= 1  # At least shadow audit


# ────────────────────────────────────────────────────────────────────────────────
# T2: STALE GUARD (HARD)
# ────────────────────────────────────────────────────────────────────────────────

def test_stale_guard_hard():
    """Test stale snapshot NEVER calls execute_genome."""
    # Setup
    stale_snapshot = create_stale_snapshot()
    mock_pump = create_mock_pump(stale_snapshot)
    genome_json = create_entry_genome()
    context_template = {"governance_level": "AUTO"}
    audit_store = MemoryAuditStore()
    
    # Mock execute_genome
    with patch("extensions.shadow_mode.loop.execute_genome") as mock_exec:
        # Create loop
        shadow_loop = loop.ShadowLoop(
            pump=mock_pump,
            genome_json=genome_json,
            context_template=context_template,
            audit_store=audit_store,
            symbol="BTCUSDT",
        )
        
        # Tick with stale snapshot
        result = shadow_loop.tick(snapshot_override=stale_snapshot)
        
        # Assertions
        assert result.status == "SKIPPED_STALE"
        assert mock_exec.call_count == 0  # CRITICAL: execute_genome NOT called
        assert result.audit_ref != ""
        
        # Verify audit shows SKIPPED_STALE
        shadow_audit = audit_store.records[-1]
        assert shadow_audit["status"] == "SKIPPED_STALE"


# ────────────────────────────────────────────────────────────────────────────────
# T3: NOOP MAPPING
# ────────────────────────────────────────────────────────────────────────────────

def test_noop_mapping():
    """Test NOOP intent mapping."""
    # Setup
    snapshot = create_fresh_snapshot()
    mock_pump = create_mock_pump(snapshot)
    genome_json = create_entry_genome()
    context_template = {"governance_level": "AUTO"}
    audit_store = MemoryAuditStore()
    
    # Mock execute_genome to return NOOP
    with patch("extensions.shadow_mode.loop.execute_genome") as mock_exec:
        mock_exec.return_value = {
            "decision_evidence": {},
            "strategy_intent": {
                "intent_id": "test_noop_123",
                "ts_ms": 1737900000000,
                "intent_type": "NOOP",
                "direction": None,
                "confidence": 0.0,
                "rationale": "No signal detected",
            },
            "proposal_card": {},
            "audit_ref": "genome_audit_noop",
            "hashes": {},
            "evidence_bundle": {},
        }
        
        # Create loop
        shadow_loop = loop.ShadowLoop(
            pump=mock_pump,
            genome_json=genome_json,
            context_template=context_template,
            audit_store=audit_store,
            symbol="BTCUSDT",
        )
        
        # Tick
        result = shadow_loop.tick(snapshot_override=snapshot)
        
        # Assertions
        assert result.status == "SKIPPED_NOOP"
        assert result.intent.signal == "NOOP"
        assert result.virtual_order is None
        assert result.audit_ref != ""
        
        # Verify audit
        shadow_audit = audit_store.records[-1]
        assert shadow_audit["status"] == "SKIPPED_NOOP"


# ────────────────────────────────────────────────────────────────────────────────
# T4: CRASH ISOLATION
# ────────────────────────────────────────────────────────────────────────────────

def test_crash_isolation():
    """Test supervisor isolates loop crashes."""
    # Setup
    snapshot_a = create_fresh_snapshot()
    snapshot_a["symbol"] = "BTCUSDT"
    snapshot_b = create_fresh_snapshot()
    snapshot_b["symbol"] = "ETHUSDT"
    
    mock_pump_a = create_mock_pump(snapshot_a)
    mock_pump_b = create_mock_pump(snapshot_b)
    
    genome_json = create_entry_genome()
    context_template = {"governance_level": "AUTO"}
    audit_store = MemoryAuditStore()
    
    # Mock execute_genome
    with patch("extensions.shadow_mode.loop.execute_genome") as mock_exec:
        # Loop A: raises exception
        def exec_side_effect_a(*args, **kwargs):
            raise ValueError("Loop A crashed!")
        
        # Loop B: returns ENTRY
        def exec_side_effect_b(*args, **kwargs):
            return {
                "decision_evidence": {},
                "strategy_intent": {
                    "intent_id": "test_loop_b",
                    "ts_ms": 1737900000000,
                    "intent_type": "ENTRY",
                    "direction": "LONG",
                    "confidence": 0.75,
                    "rationale": "Test",
                },
                "proposal_card": {},
                "audit_ref": "genome_b",
                "hashes": {},
                "evidence_bundle": {},
            }
        
        # Create loops
        loop_a = loop.ShadowLoop(
            pump=mock_pump_a,
            genome_json=genome_json,
            context_template=context_template,
            audit_store=audit_store,
            symbol="BTCUSDT",
        )
        
        loop_b = loop.ShadowLoop(
            pump=mock_pump_b,
            genome_json=genome_json,
            context_template=context_template,
            audit_store=audit_store,
            symbol="ETHUSDT",
        )
        
        # Create supervisor
        sup = supervisor.ShadowSupervisor()
        sup.add_loop("BTCUSDT", loop_a)
        sup.add_loop("ETHUSDT", loop_b)
        
        # Mock execute_genome with different behaviors
        call_count = [0]
        
        def exec_router(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call (Loop A)
                raise ValueError("Loop A crashed!")
            else:
                # Second call (Loop B)
                return exec_side_effect_b(*args, **kwargs)
        
        mock_exec.side_effect = exec_router
        
        # Run iteration
        results = sup.run_sync_iteration()
        
        # Assertions
        assert "BTCUSDT" in results
        assert "ETHUSDT" in results
        
        # Loop A should have ERROR status (crash caught)
        assert results["BTCUSDT"].status == "ERROR"
        
        # Loop B should be EXECUTED (not affected by A's crash)
        assert results["ETHUSDT"].status == "EXECUTED"
        assert results["ETHUSDT"].virtual_order is not None


# ────────────────────────────────────────────────────────────────────────────────
# T5: ADAPTER PRICE VALIDATION
# ────────────────────────────────────────────────────────────────────────────────

def test_adapter_price_validation():
    """Test adapter fails-closed on missing/invalid prices."""
    # Setup
    snapshot_missing_prices = create_fresh_snapshot()
    snapshot_missing_prices["top"]["best_bid"] = None
    snapshot_missing_prices["top"]["best_ask"] = None
    
    mock_pump = create_mock_pump(snapshot_missing_prices)
    genome_json = create_entry_genome()
    context_template = {"governance_level": "AUTO"}
    audit_store = MemoryAuditStore()
    
    # Mock execute_genome to return ENTRY
    with patch("extensions.shadow_mode.loop.execute_genome") as mock_exec:
        mock_exec.return_value = {
            "decision_evidence": {},
            "strategy_intent": {
                "intent_id": "test_price_missing",
                "ts_ms": 1737900000000,
                "intent_type": "ENTRY",
                "direction": "LONG",
                "confidence": 0.85,
                "rationale": "Test",
            },
            "proposal_card": {},
            "audit_ref": "genome_audit",
            "hashes": {},
            "evidence_bundle": {},
        }
        
        # Create loop
        shadow_loop = loop.ShadowLoop(
            pump=mock_pump,
            genome_json=genome_json,
            context_template=context_template,
            audit_store=audit_store,
            symbol="BTCUSDT",
        )
        
        # Tick
        result = shadow_loop.tick(snapshot_override=snapshot_missing_prices)
        
        # Assertions
        assert result.status == "SKIPPED_NOOP"  # Fail-closed to NOOP
        assert result.virtual_order is None
        assert result.error is not None
        assert result.error["code"] == models.ShadowErrorCode.PRICE_MISSING


# ────────────────────────────────────────────────────────────────────────────────
# T6: NO WALL-CLOCK IMPORTS (AST)
# ────────────────────────────────────────────────────────────────────────────────

def test_no_wall_clock_imports_phase13a_ast():
    """AST scan: verify no wall-clock usage in Phase 13A modules."""
    # Deterministic repo root resolution
    test_file_path = Path(__file__).resolve()
    repo_root = None
    
    for parent in test_file_path.parents:
        if (parent / "extensions").exists() and (parent / "extensions").is_dir():
            repo_root = parent
            break
    
    if repo_root is None:
        pytest.fail("Could not find repo root")
    
    # Files to scan
    files_to_scan = [
        repo_root / "extensions/shadow_mode/models.py",
        repo_root / "extensions/shadow_mode/adapter.py",
        repo_root / "extensions/shadow_mode/loop.py",
        repo_root / "extensions/shadow_mode/supervisor.py",
    ]
    
    # Forbidden call patterns
    forbidden_calls = {
        ("time", "time"): "time.time()",
        ("datetime", "now"): "datetime.now()",
        ("time", "perf_counter"): "time.perf_counter()",
    }
    
    violations = []
    
    for file_path in files_to_scan:
        if not file_path.exists():
            pytest.fail(f"Required file not found: {file_path}")
        
        with open(file_path, "r") as f:
            source = f.read()
        
        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError as e:
            pytest.fail(f"Syntax error in {file_path}: {e}")
        
        # Wall-clock detector
        class WallClockDetector(ast.NodeVisitor):
            def __init__(self):
                self.violations = []
            
            def visit_Call(self, node):
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        module = node.func.value.id
                        attr = node.func.attr
                        
                        if (module, attr) in forbidden_calls:
                            self.violations.append(
                                {
                                    "line": node.lineno,
                                    "pattern": forbidden_calls[(module, attr)],
                                }
                            )
                
                self.generic_visit(node)
        
        detector = WallClockDetector()
        detector.visit(tree)
        
        if detector.violations:
            for v in detector.violations:
                violations.append(f"{file_path.name}:{v['line']}: {v['pattern']}")
    
    if violations:
        pytest.fail(f"Wall-clock usage detected:\n" + "\n".join(violations))


# ────────────────────────────────────────────────────────────────────────────────
# T7: NO TRADE ENDPOINTS STATIC SCAN
# ────────────────────────────────────────────────────────────────────────────────

def test_no_trade_endpoints_present_static_scan():
    """Static scan for forbidden endpoint patterns."""
    test_file_path = Path(__file__).resolve()
    repo_root = None
    
    for parent in test_file_path.parents:
        if (parent / "extensions").exists():
            repo_root = parent
            break
    
    if repo_root is None:
        pytest.fail("Could not find repo root")
    
    files_to_scan = [
        repo_root / "extensions/shadow_mode/loop.py",
        repo_root / "extensions/shadow_mode/adapter.py",
    ]
    
    # Forbidden patterns
    forbidden_patterns = [
        "/order\"",
        "listenKey",
        "userDataStream",
        "/fapi",
        "/dapi",
        "/sapi",
    ]
    
    violations = []
    
    for file_path in files_to_scan:
        if not file_path.exists():
            continue
        
        with open(file_path, "r") as f:
            content = f.read()
        
        for pattern in forbidden_patterns:
            if pattern in content:
                violations.append(f"{file_path.name}: {pattern}")
    
    if violations:
        pytest.fail(f"Forbidden endpoint patterns detected:\n" + "\n".join(violations))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
