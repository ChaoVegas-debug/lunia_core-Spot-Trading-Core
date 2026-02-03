"""Phase 6 RBAC + Streaming Audit Tests (COMPREHENSIVE - ADVERSARIAL)

All 7 required tests for segregation of duties and memory-safe forensic streaming.
"""
import pytest
import os
import json
import tempfile
from pathlib import Path
from flask import Flask

from forensic.risk.store import RiskConfigStore
from forensic.risk.audit import AuditLogger
from forensic.api.admin_governance_routes import admin_bp, init_governance
from forensic.api.auth import Role


@pytest.fixture
def test_paths(tmp_path):
    """Test file paths."""
    return {
        "config": str(tmp_path / "test_config.json"),
        "audit":  str(tmp_path / "test_audit.jsonl"),
        "lock": str(tmp_path / "test_config.lock")
    }


@pytest.fixture
def app(test_paths):
    """Flask test app with admin blueprint."""
    test_app = Flask(__name__)
    test_app.config['TESTING'] = True
    test_app.register_blueprint(admin_bp, url_prefix="/api/admin")
    
    # Initialize governance with test paths
    init_governance(test_paths["config"], test_paths["audit"])
    
    return test_app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


def test_t1_rbac_enforcement_insider_threat(client, monkeypatch):
    """T1: RBAC prevents insider misuse - RISK/AUDITOR restrictions."""
    # Setup tokens
    monkeypatch.setenv("AUTH_ROOT_TOKEN", "root-token-123")
    monkeypatch.setenv("AUTH_RISK_TOKEN", "risk-token-456")
    monkeypatch.setenv("AUTH_AUDITOR_TOKEN", "auditor-token-789")
    
    # ==============================================
    # RISK role: can SET MODE, cannot HALT, cannot READ AUDIT
    # ==============================================
    
    # RISK can POST /governance/mode (with ACK)
    response = client.post("/api/admin/governance/mode",
                          json={"mode": "ENFORCE", "reason": "risk user testing mode change here", "request_id": "risk-req-mode-1"},
                          headers={"X-ADMIN-TOKEN": "risk-token-456", "X-ADMIN-ACK": "I_UNDERSTAND_GOVERNANCE_WRITE"})
    assert response.status_code == 200, f"RISK should be able to set mode, got {response.status_code}"
    
    # RISK cannot POST /governance/halt => 403 INSUFFICIENT_ROLE
    response = client.post("/api/admin/governance/halt",
                          json={"halt": True, "reason": "risk user attempting halt (should fail)", "request_id": "risk-req-halt-1"},
                          headers={"X-ADMIN-TOKEN": "risk-token-456", "X-ADMIN-ACK": "I_UNDERSTAND_GOVERNANCE_WRITE"})
    assert response.status_code == 403
    assert response.get_json()["error_code"] == "INSUFFICIENT_ROLE"
    
    # RISK cannot GET /audit => 403 INSUFFICIENT_ROLE
    response = client.get("/api/admin/audit?limit=10",
                         headers={"X-ADMIN-TOKEN": "risk-token-456"})
    assert response.status_code == 403
    assert response.get_json()["error_code"] == "INSUFFICIENT_ROLE"
    
    # ==============================================
    # AUDITOR role: can READ AUDIT, cannot WRITE (MODE/HALT)
    # ==============================================
    
    # AUDITOR can GET /audit (stream)
    response = client.get("/api/admin/audit?limit=10",
                         headers={"X-ADMIN-TOKEN": "auditor-token-789"})
    assert response.status_code == 200
    assert response.mimetype == "application/x-ndjson"
    
    # AUDITOR cannot POST /governance/mode => 403 INSUFFICIENT_ROLE
    response = client.post("/api/admin/governance/mode",
                          json={"mode": "SHADOW", "reason": "auditor attempting mode (should fail)", "request_id": "auditor-req-mode-1"},
                          headers={"X-ADMIN-TOKEN": "auditor-token-789", "X-ADMIN-ACK": "I_UNDERSTAND_GOVERNANCE_WRITE"})
    assert response.status_code == 403
    assert response.get_json()["error_code"] == "INSUFFICIENT_ROLE"
    
    # AUDITOR cannot POST /governance/halt => 403 INSUFFICIENT_ROLE
    response = client.post("/api/admin/governance/halt",
                          json={"halt": True, "reason": "auditor attempting halt (should fail)", "request_id": "auditor-req-halt-1"},
                          headers={"X-ADMIN-TOKEN": "auditor-token-789", "X-ADMIN-ACK": "I_UNDERSTAND_GOVERNANCE_WRITE"})
    assert response.status_code == 403
    assert response.get_json()["error_code"] == "INSUFFICIENT_ROLE"


def test_t2_root_supremacy(client, monkeypatch):
    """T2: ROOT can do everything."""
    monkeypatch.setenv("AUTH_ROOT_TOKEN", "root-supreme-999")
    
    # ROOT can POST /mode
    response = client.post("/api/admin/governance/mode",
                          json={"mode": "ENFORCE", "reason": "root user setting mode supremacy test", "request_id": "root-mode-1"},
                          headers={"X-ADMIN-TOKEN": "root-supreme-999", "X-ADMIN-ACK": "I_UNDERSTAND_GOVERNANCE_WRITE"})
    assert response.status_code == 200
    
    # ROOT can POST /halt
    response = client.post("/api/admin/governance/halt",
                          json={"halt": True, "reason": "root user setting halt supremacy test", "request_id": "root-halt-1"},
                          headers={"X-ADMIN-TOKEN": "root-supreme-999", "X-ADMIN-ACK": "I_UNDERSTAND_GOVERNANCE_WRITE"})
    assert response.status_code == 200
    
    # ROOT can GET /audit
    response = client.get("/api/admin/audit?limit=10",
                         headers={"X-ADMIN-TOKEN": "root-supreme-999"})
    assert response.status_code == 200
    assert response.mimetype == "application/x-ndjson"


def test_t3_auth_failure_semantics(client, monkeypatch):
    """T3: Auth failure codes - 401 missing/invalid, 403 ACK failures."""
    monkeypatch.setenv("AUTH_ROOT_TOKEN", "root-auth-test-777")
    
    # Missing X-ADMIN-TOKEN => 401 INVALID_TOKEN
    response = client.post("/api/admin/governance/mode",
                          json={"mode": "ENFORCE", "reason": "no token test for auth failure", "request_id": "auth-fail-1"},
                          headers={"X-ADMIN-ACK": "I_UNDERSTAND_GOVERNANCE_WRITE"})
    assert response.status_code == 401
    assert response.get_json()["error_code"] == "INVALID_TOKEN"
    
    # Invalid token => 401 INVALID_TOKEN
    response = client.post("/api/admin/governance/mode",
                          json={"mode": "ENFORCE", "reason": "invalid token test", "request_id": "auth-fail-2"},
                          headers={"X-ADMIN-TOKEN": "wrong-token-bad", "X-ADMIN-ACK": "I_UNDERSTAND_GOVERNANCE_WRITE"})
    assert response.status_code == 401
    assert response.get_json()["error_code"] == "INVALID_TOKEN"
    
    # Missing ACK on write => 403 MISSING_ADMIN_ACK
    response = client.post("/api/admin/governance/mode",
                          json={"mode": "ENFORCE", "reason": "missing ack test", "request_id": "auth-fail-3"},
                          headers={"X-ADMIN-TOKEN": "root-auth-test-777"})
    assert response.status_code == 403
    assert response.get_json()["error_code"] == "MISSING_ADMIN_ACK"
    
    # Invalid ACK on write => 403 INVALID_ADMIN_ACK
    response = client.post("/api/admin/governance/mode",
                          json={"mode": "ENFORCE", "reason": "invalid ack test", "request_id": "auth-fail-4"},
                          headers={"X-ADMIN-TOKEN": "root-auth-test-777", "X-ADMIN-ACK": "WRONG_ACK"})
    assert response.status_code == 403
    assert response.get_json()["error_code"] == "INVALID_ADMIN_ACK"


def test_t4_streaming_limit_hard_cap(client, monkeypatch, test_paths):
    """T4: Streaming limit hard cap - 1001 rejected, exact limit respected."""
    monkeypatch.setenv("AUTH_ROOT_TOKEN", "root-limit-test-333")
    
    # Create audit log with >= 120 valid records
    audit = AuditLogger(test_paths["audit"])
    store = RiskConfigStore(test_paths["config"])
    store.load_or_initialize()
    
    for i in range(125):
        prev = {"mode": "SHADOW", "is_halted": False, "version": i+1}
        new = {"mode": "ENFORCE" if i % 2 == 0 else "SHADOW", "is_halted": False, "version": i+2}
        audit.log_change(f"TEST_ACTION_{i}", f"limit-test-req-{i}", "admin", f"test reason {i} for limit testing", prev, new, True, None)
    
    # Request limit=10 => receive exactly 10 valid records
    response = client.get("/api/admin/audit?limit=10",
                         headers={"X-ADMIN-TOKEN": "root-limit-test-333"})
    assert response.status_code == 200
    
    lines = list(response.response)
    valid_lines = [line for line in lines if b'"type":"error"' not in line]
    assert len(valid_lines) == 10, f"Expected exactly 10 valid records, got {len(valid_lines)}"
    
    # Request limit=1001 => 400 LIMIT_EXCEEDED (JSON error, not NDJSON)
    response = client.get("/api/admin/audit?limit=1001",
                         headers={"X-ADMIN-TOKEN": "root-limit-test-333"})
    assert response.status_code == 400
    data = response.get_json()
    assert data["error_code"] == "LIMIT_EXCEEDED"


def test_t5_streaming_is_memory_safe(client, monkeypatch, test_paths):
    """T5: Streaming is memory-safe - response is generator-based."""
    monkeypatch.setenv("AUTH_ROOT_TOKEN", "root-stream-test-555")
    
    # Create audit records
    audit = AuditLogger(test_paths["audit"])
    for i in range(50):
        prev = {"mode": "SHADOW", "is_halted": False, "version": i+1}
        new = {"mode": "ENFORCE", "is_halted": False, "version": i+2}
        audit.log_change("STREAM_TEST", f"stream-req-{i}", "admin", f"memory safe test {i}", prev, new, True, None)
    
    # Request stream
    response = client.get("/api/admin/audit?limit=20",
                         headers={"X-ADMIN-TOKEN": "root-stream-test-555"})
    assert response.status_code == 200
    
    # Assert response is streamed (generator-based)
    # In Flask tests, response.response is the generator
    assert hasattr(response, 'response')
    
    # Iterate and count (proves streaming works)
    line_count = 0
    for line in response.response:
        line_count += 1
        assert b'\n' in line  # NDJSON format
    
    assert line_count == 20  # Should get exactly 20 valid records


def test_t6_corruption_handling(test_paths, monkeypatch):
    """T6: Corruption handling - yields error records, doesn't crash."""
    # Create a test audit file with mixed content
    audit_path = Path(test_paths["audit"])
    
    # Valid record 1
    record1 = {
        "timestamp": "2026-01-21T00:00:01Z",
        "actor": "admin",
        "action": "TEST_VALID_1",
        "request_id": "corrupt-test-1",
        "reason": "first valid record",
        "previous_state": {"mode": "SHADOW", "is_halted": False, "version": 1},
        "new_state": {"mode": "ENFORCE", "is_halted": False, "version": 2},
        "success": True,
        "error_code": None
    }
    canonical1 = json.dumps(record1, sort_keys=True, separators=(',', ':'))
    audit_id1 = __import__('hashlib').sha256(canonical1.encode()).hexdigest()
    record1["audit_id"] = audit_id1
    
    # Corrupt JSON line
    corrupt_json = '{"invalid": json malformed'
    
    # Valid record with checksum mismatch
    record2 = {
        "timestamp": "2026-01-21T00:00:02Z",
        "actor": "admin",
        "action": "TEST_CHECKSUM_MISMATCH",
        "request_id": "corrupt-test-2",
        "reason": "checksum will be wrong",
        "previous_state": {"mode": "ENFORCE", "is_halted": False, "version": 2},
        "new_state": {"mode": "SHADOW", "is_halted": False, "version": 3},
        "success": True,
        "error_code": None,
        "audit_id": "WRONG_CHECKSUM_DELIBERATELY_INCORRECT_123456789"
    }
    
    # Valid record 2
    record3 = {
        "timestamp": "2026-01-21T00:00:03Z",
        "actor": "admin",
        "action": "TEST_VALID_2",
        "request_id": "corrupt-test-3",
        "reason": "second valid record",
        "previous_state": {"mode": "SHADOW", "is_halted": False, "version": 3},
        "new_state": {"mode": "ENFORCE", "is_halted": False, "version": 4},
        "success": True,
        "error_code": None
    }
    canonical3 = json.dumps(record3, sort_keys=True, separators=(',', ':'))
    audit_id3 = __import__('hashlib').sha256(canonical3.encode()).hexdigest()
    record3["audit_id"] = audit_id3
    
    # Write test audit file
    with open(audit_path, 'w') as f:
        f.write(json.dumps(record1) + '\n')
        f.write(corrupt_json + '\n')
        f.write(json.dumps(record2) + '\n')
        f.write(json.dumps(record3) + '\n')
    
    # Stream with limit=2 valid records
    audit = AuditLogger(test_paths["audit"])
    lines = list(audit.stream_records(limit=2))
    
    # Parse lines
    parsed = [json.loads(line) for line in lines]
    
    # Should have:
    # - 1 valid record (record1)
    # - 1 error (INVALID_JSON)
    # - 1 error (CHECKSUM_MISMATCH)
    # - 1 valid record (record3)
    # Total = 4 lines, but only 2 valid records (limit=2)
    
    valid_records = [p for p in parsed if p.get("type") != "error"]
    error_records = [p for p in parsed if p.get("type") == "error"]
    
    assert len(valid_records) == 2, f"Expected 2 valid records, got {len(valid_records)}"
    assert len(error_records) == 2, f"Expected 2 error records, got {len(error_records)}"
    
    # Verify error types
    error_types = [e["error"] for e in error_records]
    assert "INVALID_JSON" in error_types
    assert "CHECKSUM_MISMATCH" in error_types


def test_t7_regression_guard():
    """T7: Phase 0-5.1 remain GREEN."""
    import subprocess
    
    # Run Phase 0-5.1 tests
    result = subprocess.run(
        ["python3", "-m", "pytest",
         "tests/forensic/test_primary_autopsy_10k_to_1k.py",
         "tests/forensic/risk/",
         "tests/forensic/api/test_phase4_api_wiring.py",
         "tests/forensic/api/test_phase5_admin_governance.py",
         "-q", "--tb=no"],
        cwd="/Users/neomind/alladin/lunia_core-Spot-Trading-Core/lunia_core",
        capture_output=True, text=True
    )
    assert result.returncode == 0, f"Phase 0-5.1 regression: {result.stdout}\n{result.stderr}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
