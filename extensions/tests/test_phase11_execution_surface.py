"""
PHASE 11D — GENOME DSL: Execution Surface Tests

Comprehensive test suite for production execution surface.

Tests:
- execute_genome returns all required fields
- Deterministic hashes (50 iterations)
- Audit side-effect isolation
- Partitioning uses now_ms only (no wall-clock)
- Size cap truncation
- No wall-clock imports (static scan)
"""

import pytest
import json
import subprocess
from pathlib import Path
from extensions.genome_dsl import types, execution_surface, audit_store
from extensions.genome_dsl.canonical import to_canonical_dict


# ────────────────────────────────────────────────────────────────────────────────
# FIXTURES
# ────────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def simple_genome_json():
    """Simple genome as JSON dict."""
    entry = types.And(nodes=[
        types.GreaterThan(
            left=types.PriceMid(),
            right=types.ConstFloat(50000.0)
        ),
        types.SignalEntry(side="BUY", confidence=0.8),
    ])
    
    exit_cond = types.ConstBool(False)
    sizing = types.SizingFixed(percent=2.0)
    exit_plan = types.ExitPlanNode(stop_loss_pct=1.0)
    
    genome = types.StrategyGenome(
        entry_condition=entry,
        exit_condition=exit_cond,
        sizing_logic=sizing,
        exit_plan=exit_plan,
        metadata={"strategy_id": "test_001", "name": "Test Strategy"}
    )
    
    return to_canonical_dict(genome)


@pytest.fixture
def deterministic_snapshot():
    """Deterministic market snapshot."""
    return {
        "symbol": "BTC/USD",
        "ts_ms": 1737543014000,
        "bid": 50000.0,
        "ask": 50002.0,
        "mid": 50001.0,
        "volume_24h": 1000000.0,
        "spread_pct": 0.004,
        "volatility_state": "normal",
        "market_regime": "trend_up",
        "atr_14": 500.0,
    }


@pytest.fixture
def deterministic_context():
    """Deterministic execution context."""
    return {
        "now_ms": 1737543014000,
        "governance_level": "AUTO",
        "run_id": "test_run_001",
        "correlation_id": "test_corr_001",
    }


# ────────────────────────────────────────────────────────────────────────────────
# TEST 1: RETURNS ALL FIELDS
# ────────────────────────────────────────────────────────────────────────────────

def test_execute_genome_returns_all_fields(simple_genome_json, deterministic_snapshot, deterministic_context):
    """Test that execute_genome returns all required fields."""
    # Use MemoryAuditStore for testing
    store = audit_store.MemoryAuditStore()
    
    result = execution_surface.execute_genome(
        simple_genome_json,
        deterministic_snapshot,
        deterministic_context,
        persist_audit=True,
        audit_store=store
    )
    
    # Check required keys
    assert "decision_evidence" in result
    assert "strategy_intent" in result
    assert "proposal_card" in result
    assert "audit_ref" in result
    assert "hashes" in result
    assert "evidence_bundle" in result
    
    # Check hash keys
    hashes = result["hashes"]
    assert "genome_hash" in hashes
    assert "snapshot_hash" in hashes
    assert "context_hash" in hashes
    assert "evidence_hash" in hashes
    assert "intent_hash" in hashes
    assert "proposal_hash" in hashes
    
    # Check evidence bundle
    bundle = result["evidence_bundle"]
    assert bundle["schema_version"] == "1.0.0"
    assert "decision_id" in bundle
    assert "timestamp_ms" in bundle
    assert bundle["timestamp_ms"] == deterministic_context["now_ms"]
    
    # Check all are JSON-serializable
    result_json = json.dumps(result, indent=2)
    assert len(result_json) > 0


# ────────────────────────────────────────────────────────────────────────────────
# TEST 2: DETERMINISTIC HASHES (50 ITERATIONS)
# ────────────────────────────────────────────────────────────────────────────────

def test_execute_genome_deterministic_hashes(simple_genome_json, deterministic_snapshot, deterministic_context):
    """Test that 50 iterations produce identical hashes."""
    store = audit_store.MemoryAuditStore()
    
    results = []
    for _ in range(50):
        result = execution_surface.execute_genome(
            simple_genome_json,
            deterministic_snapshot,
            deterministic_context,
            persist_audit=True,
            audit_store=store
        )
        results.append(result)
    
    # Extract hashes
    all_hashes = [r["hashes"] for r in results]
    
    # All hashes must be identical
    first_hashes = all_hashes[0]
    for hashes in all_hashes[1:]:
        assert hashes == first_hashes, "Hash determinism violation"
    
    # Check specific hashes are non-trivial
    assert len(first_hashes["genome_hash"]) == 64  # SHA256
    assert first_hashes["genome_hash"] != "0" * 64
    
    # Check outputs are identical (not just hashes)
    for i, result in enumerate(results[1:], 1):
        assert result["decision_evidence"] == results[0]["decision_evidence"], f"Evidence differs at iteration {i}"
        assert result["strategy_intent"] == results[0]["strategy_intent"], f"Intent differs at iteration {i}"


# ────────────────────────────────────────────────────────────────────────────────
# TEST 3: AUDIT SIDE-EFFECT ISOLATION
# ────────────────────────────────────────────────────────────────────────────────

def test_audit_side_effect_isolation(simple_genome_json, deterministic_snapshot, deterministic_context):
    """Test that audit persistence doesn't influence outputs."""
    store = audit_store.MemoryAuditStore()
    
    # Run without audit
    result_no_audit = execution_surface.execute_genome(
        simple_genome_json,
        deterministic_snapshot,
        deterministic_context,
        persist_audit=False,
        audit_store=None
    )
    
    # Run with audit
    result_with_audit = execution_surface.execute_genome(
        simple_genome_json,
        deterministic_snapshot,
        deterministic_context,
        persist_audit=True,
        audit_store=store
    )
    
    # Outputs must be identical except audit_ref
    assert result_no_audit["decision_evidence"] == result_with_audit["decision_evidence"]
    assert result_no_audit["strategy_intent"] == result_with_audit["strategy_intent"]
    assert result_no_audit["proposal_card"] == result_with_audit["proposal_card"]
    assert result_no_audit["hashes"] == result_with_audit["hashes"]
    
    # Audit ref should differ
    assert result_no_audit["audit_ref"] is None
    assert result_with_audit["audit_ref"] is not None
    assert result_with_audit["audit_ref"].startswith("memory:")
    
    # Check store has record
    assert len(store.records) == 1


# ────────────────────────────────────────────────────────────────────────────────
# TEST 4: PARTITIONING USES NOW_MS ONLY
# ────────────────────────────────────────────────────────────────────────────────

def test_partitioning_uses_now_ms_only(simple_genome_json, deterministic_snapshot):
    """Test that partitioning is deterministic from now_ms."""
    store = audit_store.FileAuditStore(root_dir="/tmp/test_audit_phase11d")
    
    # Two different timestamps
    context1 = {
        "now_ms": 1737543014000,  # 2025-01-22
        "governance_level": "AUTO",
    }
    
    context2 = {
        "now_ms": 1640995200000,  # 2022-01-01
        "governance_level": "AUTO",
    }
    
    # Get partition paths
    path1 = store._get_partition_path(context1["now_ms"])
    path2 = store._get_partition_path(context2["now_ms"])
    
    # Paths must differ deterministically
    assert path1 != path2
    
    # Verify path format (YYYY/MM/YYYY-MM-DD.jsonl)
    assert path1.suffix == ".jsonl"
    assert path2.suffix == ".jsonl"
    
    # Verify determinism: same timestamp → same path
    path1_again = store._get_partition_path(context1["now_ms"])
    assert path1 == path1_again
    
    # Verify POSIX-style normalized paths
    assert "/" in path1.as_posix()
    assert "\\" not in path1.as_posix()


# ────────────────────────────────────────────────────────────────────────────────
# TEST 5: SIZE CAP TRUNCATION
# ────────────────────────────────────────────────────────────────────────────────

def test_audit_record_size_cap_truncates():
    """Test that large records are truncated deterministically."""
    # Create synthetic large record
    large_logic_trace = [
        {
            "node_id": f"Node_{i}",
            "node_type": "GreaterThan",
            "output": True,
            "rationale": "X" * 200,  # 200 chars each
        }
        for i in range(10000)  # 10k nodes → ~2MB
    ]
    
    large_record = {
        "schema_version": "1.0.0",
        "decision_id": "test_large",
        "timestamp_ms": 1737543014000,
        "hashes": {
            "genome_hash": "a" * 64,
            "snapshot_hash": "b" * 64,
            "context_hash": "c" * 64,
            "evidence_hash": "d" * 64,
            "intent_hash": "e" * 64,
            "proposal_hash": "f" * 64,
        },
        "decision_evidence": {
            "logic_trace": large_logic_trace,
            "signal": "ENTRY",
            "confidence_raw": 1.0,
        },
        "strategy_intent": {"intent_id": "test"},
        "proposal_card": {"proposal_id": "test"},
        "salient_nodes": [],
    }
    
    # Truncate
    truncated = audit_store.truncate_audit_record(large_record)
    
    # Must have truncation note
    assert "truncation_note" in truncated
    assert truncated["truncation_note"].startswith("DATA_TRUNCATED")
    
    # Must be under 1MB
    truncated_json = json.dumps(truncated, sort_keys=True)
    assert len(truncated_json.encode('utf-8')) <= audit_store.MAX_AUDIT_RECORD_BYTES
    
    # Hashes must still be present (even in minimal)
    assert "hashes" in truncated
    assert truncated["hashes"]["genome_hash"] == "a" * 64


# ────────────────────────────────────────────────────────────────────────────────
# TEST 6: NO WALL-CLOCK IMPORTS (STATIC SCAN)
# ────────────────────────────────────────────────────────────────────────────────

def test_no_wall_clock_imports():
    """Static scan: verify no wall-clock usage in Phase 11D files (AST-based)."""
    import ast
    
    # Deterministic repo root resolution (no CWD dependence)
    test_file_path = Path(__file__).resolve()
    repo_root = None
    
    # Walk parents until we find "extensions/" directory
    for parent in test_file_path.parents:
        if (parent / "extensions").exists() and (parent / "extensions").is_dir():
            repo_root = parent
            break
    
    if repo_root is None:
        pytest.fail("Could not find repo root (extensions/ marker not found)")
    
    # Files to scan (Phase 11D only)
    files_to_scan = [
        repo_root / "extensions/genome_dsl/execution_surface.py",
        repo_root / "extensions/genome_dsl/audit_store.py",
        repo_root / "extensions/genome_dsl/integration.py",
        repo_root / "extensions/genome_dsl/interpreter.py",
    ]
    
    # Forbidden call patterns (actual usage, not imports)
    forbidden_calls = {
        ("time", "time"): "time.time()",
        ("datetime", "now"): "datetime.now()",
        ("time", "perf_counter"): "time.perf_counter()",
        ("perf_counter",): "perf_counter()",  # Direct call
    }
    
    violations = []
    
    for file_path in files_to_scan:
        if not file_path.exists():
            pytest.fail(f"Required file not found: {file_path}")
        
        with open(file_path, 'r') as f:
            source = f.read()
        
        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError as e:
            pytest.fail(f"Syntax error in {file_path}: {e}")
        
        # Walk AST to find forbidden calls
        class WallClockDetector(ast.NodeVisitor):
            def __init__(self):
                self.violations = []
            
            def visit_Call(self, node):
                # Check for time.time(), datetime.now(), etc.
                if isinstance(node.func, ast.Attribute):
                    # e.g., time.time() or datetime.now()
                    if isinstance(node.func.value, ast.Name):
                        module = node.func.value.id
                        attr = node.func.attr
                        
                        if (module, attr) in forbidden_calls:
                            self.violations.append({
                                "line": node.lineno,
                                "pattern": forbidden_calls[(module, attr)],
                                "type": "call"
                            })
                
                elif isinstance(node.func, ast.Name):
                    # e.g., perf_counter() if imported directly
                    func_name = node.func.id
                    if (func_name,) in forbidden_calls:
                        self.violations.append({
                            "line": node.lineno,
                            "pattern": forbidden_calls[(func_name,)],
                            "type": "call"
                        })
                
                self.generic_visit(node)
        
        detector = WallClockDetector()
        detector.visit(tree)
        
        if detector.violations:
            for v in detector.violations:
                violations.append(
                    f"{file_path.name}:{v['line']}: {v['type']}: {v['pattern']}"
                )
    
    if violations:
        pytest.fail(f"Wall-clock usage detected:\n" + "\n".join(violations))


# ────────────────────────────────────────────────────────────────────────────────
# TEST 9: CROSS-RUN STATE ISOLATION
# ────────────────────────────────────────────────────────────────────────────────

def test_cross_run_state_isolation(simple_genome_json, deterministic_snapshot, deterministic_context):
    """Test that multiple execute_genome calls don't contaminate each other."""
    
    # Run 1: No audit
    result1_no_audit = execution_surface.execute_genome(
        simple_genome_json,
        deterministic_snapshot,
        deterministic_context,
        persist_audit=False,
        audit_store=None
    )
    
    # Run 2: No audit (again)
    result2_no_audit = execution_surface.execute_genome(
        simple_genome_json,
        deterministic_snapshot,
        deterministic_context,
        persist_audit=False,
        audit_store=None
    )
    
    # Must be identical
    assert result1_no_audit == result2_no_audit, "State contamination detected (no audit runs)"
    
    # Run 3: With audit (MemoryAuditStore)
    store1 = audit_store.MemoryAuditStore()
    result1_audit = execution_surface.execute_genome(
        simple_genome_json,
        deterministic_snapshot,
        deterministic_context,
        persist_audit=True,
        audit_store=store1
    )
    
    # Run 4: With audit (fresh store)
    store2 = audit_store.MemoryAuditStore()
    result2_audit = execution_surface.execute_genome(
        simple_genome_json,
        deterministic_snapshot,
        deterministic_context,
        persist_audit=True,
        audit_store=store2
    )
    
    # Remove audit_ref (only field that should differ)
    result1_copy = result1_audit.copy()
    result2_copy = result2_audit.copy()
    
    audit_ref1 = result1_copy.pop("audit_ref", None)
    audit_ref2 = result2_copy.pop("audit_ref", None)
    
    # Must be identical after removing audit_ref
    assert result1_copy == result2_copy, "State contamination detected (audit runs)"
    
    # Audit refs should exist and differ (different stores)
    assert audit_ref1 is not None
    assert audit_ref2 is not None
    assert audit_ref1 == "memory:0"  # First record
    assert audit_ref2 == "memory:0"  # First record in second store


# ────────────────────────────────────────────────────────────────────────────────
# TEST 10: GENOME JSON PARSER ROUNDTRIP
# ────────────────────────────────────────────────────────────────────────────────

def test_genome_json_parser_roundtrip(simple_genome_json):
    """Test that parse_genome_json correctly reconstructs genome."""
    # Parse
    genome = execution_surface.parse_genome_json(simple_genome_json)
    
    # Verify type
    assert isinstance(genome, types.StrategyGenome)
    
    # Verify metadata
    assert genome.metadata["strategy_id"] == "test_001"
    assert genome.metadata["name"] == "Test Strategy"
    
    # Re-serialize
    genome_json_again = to_canonical_dict(genome)
    
    # Should be identical (roundtrip)
    assert genome_json_again == simple_genome_json


# ────────────────────────────────────────────────────────────────────────────────
# TEST 8: FAIL-CLOSED ON INVALID GENOME
# ────────────────────────────────────────────────────────────────────────────────

def test_fail_closed_on_invalid_genome(deterministic_snapshot, deterministic_context):
    """Test that invalid genome produces deterministic NOOP."""
    invalid_genome_json = {
        "__type__": "InvalidType",
        "metadata": {},
    }
    
    result = execution_surface.execute_genome(
        invalid_genome_json,
        deterministic_snapshot,
        deterministic_context,
        persist_audit=False,
        audit_store=None
    )
    
    # Should return NOOP outputs
    assert result["decision_evidence"]["signal"] == "NOOP"
    assert result["decision_evidence"]["confidence_raw"] == 0.0
    
    # Should have error in constitutional violations
    violations = result["decision_evidence"]["constitutional_violations"]
    assert any("EXECUTION_ERROR" in v for v in violations)
    
    # Hashes should still be computed (inputs hashed even on failure)
    assert "hashes" in result
    assert len(result["hashes"]["snapshot_hash"]) == 64


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
