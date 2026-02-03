"""
PHASE 11E — AUDIT RETRIEVAL API: Tests

Comprehensive test suite for read-only audit retrieval.

Tests:
- List partitions (deterministic sorting)
- Pagination cursor stability
- Get record by ref (exact line + traversal protection)
- Filters (exact match)
- Compaction (size bound)
- No wall-clock imports (AST scan)
"""

import pytest
import json
import ast
import tempfile
from pathlib import Path
from extensions.audit_api import retrieval
from extensions.genome_dsl import audit_store


# ────────────────────────────────────────────────────────────────────────────────
# FIXTURES
# ────────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def temp_audit_dir():
    """Temporary audit directory with sample partitions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        
        # Create partitions with deterministic records
        partitions = [
            "2025/01/2025-01-22.jsonl",
            "2025/01/2025-01-23.jsonl",
            "2025/02/2025-02-01.jsonl",
        ]
        
        for partition in partitions:
            part_path = root / partition
            part_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write sample records
            with open(part_path, 'w') as f:
                for i in range(5):
                    record = {
                        "schema_version": "1.0.0",
                        "decision_id": f"decision_{partition}_{i}",
                        "timestamp_ms": 1737543014000 + i * 1000,  # Incrementing timestamps
                        "hashes": {
                            "genome_hash": "a" * 64,
                            "snapshot_hash": "b" * 64,
                            "context_hash": "c" * 64,
                            "evidence_hash": "d" * 64,
                            "intent_hash": "e" * 64,
                            "proposal_hash": "f" * 64,
                        },
                        "decision_evidence": {"signal": "ENTRY" if i % 2 == 0 else "EXIT"},
                        "strategy_intent": {"confidence": 0.8 + i * 0.01},
                    }
                    f.write(json.dumps(record) + '\n')
        
        yield root


# ────────────────────────────────────────────────────────────────────────────────
# T1: LIST PARTITIONS (DETERMINISTIC SORTING)
# ────────────────────────────────────────────────────────────────────────────────

def test_list_partitions_sorted_deterministically(temp_audit_dir):
    """Test that partitions are listed in deterministic sorted order."""
    partitions = retrieval.list_audit_partitions(temp_audit_dir)
    
    # Must be sorted
    assert partitions == sorted(partitions)
    
    # Must be POSIX paths
    for p in partitions:
        assert '\\' not in p
        assert '/' in p or len(p.split('/')) == 1
    
    # Expected partitions
    assert len(partitions) == 3
    assert "2025/01/2025-01-22.jsonl" in partitions
    assert "2025/01/2025-01-23.jsonl" in partitions
    assert "2025/02/2025-02-01.jsonl" in partitions
    
    # Verify ordering (lexicographic)
    assert partitions[0] == "2025/01/2025-01-22.jsonl"
    assert partitions[1] == "2025/01/2025-01-23.jsonl"
    assert partitions[2] == "2025/02/2025-02-01.jsonl"


# ────────────────────────────────────────────────────────────────────────────────
# T2: PAGINATION CURSOR STABILITY
# ────────────────────────────────────────────────────────────────────────────────

def test_list_records_pagination_stable(temp_audit_dir):
    """Test cursor-based pagination produces stable results."""
    # First page
    page1 = retrieval.list_audit_records(temp_audit_dir, limit=5, order="asc")
    
    assert "items" in page1
    assert "next_cursor" in page1
    assert "stats" in page1
    
    # Should have 5 items
    assert len(page1["items"]) == 5
    
    # Should have next cursor
    assert page1["next_cursor"] is not None
    
    # Second page (using cursor)
    page2 = retrieval.list_audit_records(
        temp_audit_dir,
        cursor=page1["next_cursor"],
        limit=5,
        order="asc"
    )
    
    assert len(page2["items"]) == 5
    
    # Pages should not overlap
    page1_refs = {item["audit_ref"] for item in page1["items"]}
    page2_refs = {item["audit_ref"] for item in page2["items"]}
    
    assert page1_refs.isdisjoint(page2_refs), "Pages overlap (not stable)"
    
    # Each page should be internally sorted (asc)
    page1_timestamps = [item["timestamp_ms"] for item in page1["items"]]
    page2_timestamps = [item["timestamp_ms"] for item in page2["items"]]
    
    assert page1_timestamps == sorted(page1_timestamps), "Page 1 not sorted (asc)"
    assert page2_timestamps == sorted(page2_timestamps), "Page 2 not sorted (asc)"
    
    # Test descending order
    page_desc = retrieval.list_audit_records(temp_audit_dir, limit=5, order="desc")
    timestamps_desc = [item["timestamp_ms"] for item in page_desc["items"]]
    assert timestamps_desc == sorted(timestamps_desc, reverse=True), "Timestamps not monotonic (desc)"


# ────────────────────────────────────────────────────────────────────────────────
# T3: GET RECORD BY REF (EXACT LINE + TRAVERSAL PROTECTION)
# ────────────────────────────────────────────────────────────────────────────────

def test_get_record_by_ref_exact_line(temp_audit_dir):
    """Test exact line retrieval and traversal protection."""
    # Get first partition's first record
    audit_ref = "file:2025/01/2025-01-22.jsonl:0"
    
    record = retrieval.get_audit_record(temp_audit_dir, audit_ref)
    
    # Should not have error
    assert "error" not in record
    
    # Should have audit_ref echoed
    assert record["audit_ref"] == audit_ref
    
    # Should have source
    assert record["source"]["type"] == "file"
    assert record["source"]["partition"] == "2025/01/2025-01-22.jsonl"
    assert record["source"]["line_index"] == 0
    
    # Should have decision_id
    assert "decision_id" in record
    
    # Test line 2
    audit_ref2 = "file:2025/01/2025-01-22.jsonl:2"
    record2 = retrieval.get_audit_record(temp_audit_dir, audit_ref2)
    assert record2["source"]["line_index"] == 2
    
    # Test traversal protection: ".."
    bad_ref1 = "file:../../../etc/passwd:0"
    result1 = retrieval.get_audit_record(temp_audit_dir, bad_ref1)
    assert "error" in result1
    assert result1["error"]["code"] == "INVALID_PATH"
    
    # Test traversal protection: absolute path
    bad_ref2 = "file:/etc/passwd:0"
    result2 = retrieval.get_audit_record(temp_audit_dir, bad_ref2)
    assert "error" in result2
    assert result2["error"]["code"] == "INVALID_PATH"
    
    # Test invalid ref format
    bad_ref3 = "invalid_format"
    result3 = retrieval.get_audit_record(temp_audit_dir, bad_ref3)
    assert "error" in result3
    assert result3["error"]["code"] == "INVALID_REF"


# ────────────────────────────────────────────────────────────────────────────────
# T4: FILTERS (EXACT MATCH)
# ────────────────────────────────────────────────────────────────────────────────

def test_filters_exact_match_deterministic(temp_audit_dir):
    """Test exact-match filters are deterministic."""
    # Filter by signal
    result_entry = retrieval.list_audit_records(
        temp_audit_dir,
        filters={"signal": "ENTRY"},
        limit=100
    )
    
    # All items should have ENTRY signal
    for item in result_entry["items"]:
        assert item["signal"] == "ENTRY"
    
    # Should have some items (ENTRY appears every other record)
    assert len(result_entry["items"]) > 0
    
    # Filter by timestamp range
    result_ts = retrieval.list_audit_records(
        temp_audit_dir,
        filters={
            "min_ts": 1737543014000,
            "max_ts": 1737543014002000,
        },
        limit=100
    )
    
    # All items should be in range
    for item in result_ts["items"]:
        assert 1737543014000 <= item["timestamp_ms"] <= 1737543014002000
    
    # Filter by decision_id (exact)
    result_id = retrieval.list_audit_records(
        temp_audit_dir,
        filters={"decision_id": "decision_2025/01/2025-01-22.jsonl_0"},
        limit=100
    )
    
    # Should have exactly one item
    assert len(result_id["items"]) == 1
    assert result_id["items"][0]["decision_id"] == "decision_2025/01/2025-01-22.jsonl_0"


# ────────────────────────────────────────────────────────────────────────────────
# T5: COMPACTION (SIZE BOUND)
# ────────────────────────────────────────────────────────────────────────────────

def test_compaction_size_bound():
    """Test that compaction enforces size bound deterministically."""
    # Create large record
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
            "signal": "ENTRY",
            "logic_trace": [
                {"node_type": "GreaterThan", "rationale": "x" * 500}
                for _ in range(1000)
            ]
        },
        "strategy_intent": {"confidence": 0.8},
        "salient_nodes": [
            {"node_type": "And", "severity": "INFO", "rationale": "y" * 300}
            for _ in range(10)
        ],
    }
    
    # Compact with small max_bytes
    compact = retrieval.compact_audit_record(large_record, max_bytes=2000)
    
    # Must have compaction_note
    assert "compaction_note" in compact
    
    # Must be under 2KB
    compact_json = json.dumps(compact, separators=(',', ':'))
    assert len(compact_json) <= 2000
    
    # Must preserve essential fields
    assert compact["timestamp_ms"] == 1737543014000
    assert compact["decision_id"] == "test_large"
    assert "hashes" in compact
    
    # Test minimal compaction (very small limit)
    minimal = retrieval.compact_audit_record(large_record, max_bytes=500)
    assert "compaction_note" in minimal
    assert len(json.dumps(minimal, separators=(',', ':'))) <= 500


# ────────────────────────────────────────────────────────────────────────────────
# T6: NO WALL-CLOCK IMPORTS (AST SCAN)
# ────────────────────────────────────────────────────────────────────────────────

def test_no_wall_clock_imports_phase11e():
    """AST scan: verify no wall-clock usage or imports in retrieval module."""
    # Deterministic repo root resolution
    test_file_path = Path(__file__).resolve()
    repo_root = None
    
    for parent in test_file_path.parents:
        if (parent / "extensions").exists() and (parent / "extensions").is_dir():
            repo_root = parent
            break
    
    if repo_root is None:
        pytest.fail("Could not find repo root")
    
    # File to scan
    file_to_scan = repo_root / "extensions/audit_api/retrieval.py"
    
    if not file_to_scan.exists():
        pytest.fail(f"Required file not found: {file_to_scan}")
    
    with open(file_to_scan, 'r') as f:
        source = f.read()
    
    try:
        tree = ast.parse(source, filename=str(file_to_scan))
    except SyntaxError as e:
        pytest.fail(f"Syntax error: {e}")
    
    # Check forbidden imports
    class ImportDetector(ast.NodeVisitor):
        def __init__(self):
            self.forbidden_imports = []
        
        def visit_Import(self, node):
            for alias in node.names:
                if alias.name in ["time", "datetime"]:
                    self.forbidden_imports.append({
                        "line": node.lineno,
                        "module": alias.name,
                        "type": "import"
                    })
            self.generic_visit(node)
        
        def visit_ImportFrom(self, node):
            if node.module in ["time", "datetime"]:
                self.forbidden_imports.append({
                    "line": node.lineno,
                    "module": node.module,
                    "type": "from_import"
                })
            self.generic_visit(node)
    
    # Check forbidden calls
    class WallClockDetector(ast.NodeVisitor):
        def __init__(self):
            self.violations = []
        
        def visit_Call(self, node):
            if isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name):
                    module = node.func.value.id
                    attr = node.func.attr
                    
                    forbidden = {
                        ("time", "time"),
                        ("datetime", "now"),
                        ("time", "perf_counter"),
                    }
                    
                    if (module, attr) in forbidden:
                        self.violations.append({
                            "line": node.lineno,
                            "pattern": f"{module}.{attr}()",
                        })
            
            self.generic_visit(node)
    
    import_detector = ImportDetector()
    import_detector.visit(tree)
    
    call_detector = WallClockDetector()
    call_detector.visit(tree)
    
    # Fail if forbidden imports found
    if import_detector.forbidden_imports:
        violations = [f"Line {v['line']}: {v['type']} {v['module']}" for v in import_detector.forbidden_imports]
        pytest.fail(f"Forbidden imports detected:\n" + "\n".join(violations))
    
    # Fail if forbidden calls found
    if call_detector.violations:
        violations = [f"Line {v['line']}: {v['pattern']}" for v in call_detector.violations]
        pytest.fail(f"Wall-clock calls detected:\n" + "\n".join(violations))


# ────────────────────────────────────────────────────────────────────────────────
# T7: VERIFY RECORD (STRUCTURAL)
# ────────────────────────────────────────────────────────────────────────────────

def test_verify_record_structural():
    """Test record verification (no re-execution)."""
    # Valid record
    valid_record = {
        "schema_version": "1.0.0",
        "timestamp_ms": 1737543014000,
        "decision_id": "test_001",
        "hashes": {
            "genome_hash": "a" * 64,
            "snapshot_hash": "b" * 64,
            "context_hash": "c" * 64,
            "evidence_hash": "d" * 64,
            "intent_hash": "e" * 64,
            "proposal_hash": "f" * 64,
        },
    }
    
    result = retrieval.verify_audit_record(valid_record)
    
    assert result["ok"] is True
    assert result["checks"]["has_required_keys"] is True
    assert result["checks"]["hash_fields_present"] is True
    assert result["checks"]["timestamp_valid"] is True
    assert len(result["notes"]) == 0
    
    # Invalid record (missing fields)
    invalid_record = {
        "decision_id": "test_002",
    }
    
    result2 = retrieval.verify_audit_record(invalid_record)
    
    assert result2["ok"] is False
    assert result2["checks"]["has_required_keys"] is False
    assert len(result2["notes"]) > 0


# ────────────────────────────────────────────────────────────────────────────────
# T8: MEMORY STORE INTEGRATION
# ────────────────────────────────────────────────────────────────────────────────

def test_memory_store_integration():
    """Test retrieval from MemoryAuditStore."""
    store = audit_store.MemoryAuditStore()
    
    # Add records
    for i in range(3):
        record = {
            "schema_version": "1.0.0",
            "decision_id": f"mem_{i}",
            "timestamp_ms": 1737543014000 + i * 1000,
            "hashes": {},
        }
        store.append(record)
    
    # Get record by memory ref
    audit_ref = "memory:1"
    record = retrieval.get_audit_record("/tmp", audit_ref, memory_store=store)
    
    assert "error" not in record
    assert record["decision_id"] == "mem_1"
    assert record["source"]["type"] == "memory"
    assert record["source"]["index"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
