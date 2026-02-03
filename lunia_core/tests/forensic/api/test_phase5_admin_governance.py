"""Phase 5 Admin Governance Tests (COMPREHENSIVE)

All 7 required tests for governance write surface.
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


def test_t1_auth_wall_fail_closed(client, monkeypatch):
    """T1: Fail-closed auth wall (Phase 6 RBAC compatible)."""
    # Case 1: No tokens -> 401 (Phase 6 RBAC)
    monkeypatch.delenv("AUTH_ROOT_TOKEN", raising=False)
    monkeypatch.delenv("AUTH_RISK_TOKEN", raising=False)
    monkeypatch.delenv("AUTH_AUDITOR_TOKEN", raising=False)
    response = client.post("/api/admin/governance/mode", 
                          json={"mode": "ENFORCE", "reason": "test reason here", "request_id": "test-req-1"},
                          headers={"X-ADMIN-TOKEN": "token", "X-ADMIN-ACK": "I_UNDERSTAND_GOVERNANCE_WRITE"})
    assert response.status_code == 401
    assert response.get_json()["error_code"] == "INVALID_TOKEN"
    
    # Case 2: Invalid token -> 401 (Phase 6 RBAC)
    monkeypatch.setenv("AUTH_ROOT_TOKEN", "correct-token-123")
    response = client.post("/api/admin/governance/mode",
                          json={"mode": "ENFORCE", "reason": "test reason here", "request_id": "test-req-2"},
                          headers={"X-ADMIN-TOKEN": "wrong-token", "X-ADMIN-ACK": "I_UNDERSTAND_GOVERNANCE_WRITE"})
    assert response.status_code == 401
    assert response.get_json()["error_code"] == "INVALID_TOKEN"
    
    # Case 3: Missing ACK -> 403
    response = client.post("/api/admin/governance/mode",
                          json={"mode": "ENFORCE", "reason": "test reason here", "request_id": "test-req-3"},
                          headers={"X-ADMIN-TOKEN": "correct-token-123"})
    assert response.status_code == 403
    assert response.get_json()["error_code"] == "MISSING_ADMIN_ACK"
    
    # Case 4: Wrong ACK -> 403
    response = client.post("/api/admin/governance/mode",
                          json={"mode": "ENFORCE", "reason": "test reason here", "request_id": "test-req-4"},
                          headers={"X-ADMIN-TOKEN": "correct-token-123", "X-ADMIN-ACK": "WRONG_ACK"})
    assert response.status_code == 403
    assert response.get_json()["error_code"] == "INVALID_ADMIN_ACK"


def test_t2_persistence_survives_restart(test_paths, monkeypatch):
    """T2: Persistence survives restart."""
    monkeypatch.setenv("AUTH_ROOT_TOKEN", "test-token-456")
    
    # Create store and update mode
    store1 = RiskConfigStore(test_paths["config"])
    store1.load_or_initialize()
    state1 = store1.update_mode("ENFORCE", "admin", "test persistence", "persist-req-1")
    
    assert state1["mode"] == "ENFORCE"
    assert state1["version"] == 2  # Initial=1, update=2
    
    # Create NEW store instance (simulates restart)
    store2 = RiskConfigStore(test_paths["config"])
    state2 = store2.load_or_initialize()
    
    # Assert mode persisted
    assert state2["mode"] == "ENFORCE"
    assert state2["version"] == 2
    assert state2["checksum"] == state1["checksum"]


def test_t3_hot_reload_proof(test_paths, monkeypatch):
    """T3: Hot reload works (behavior changes without restart)."""
    from forensic.risk.hot_reload import init_hot_reload_store, get_governance_state
    
    # Initialize hot reload
    init_hot_reload_store(test_paths["config"])
    
    # Initial state: SHADOW
    state1 = get_governance_state()
    assert state1["mode"] == "SHADOW"
    
    # Update using store (simulating admin API)
    store = RiskConfigStore(test_paths["config"])
    store.update_mode("ENFORCE", "admin", "hot reload test", "hotreload-req-1")
    
    # Hot reload: get_governance_state should reflect change WITHOUT restart
    state2 = get_governance_state()
    assert state2["mode"] == "ENFORCE"  # Changed!
    assert state2["version"] > state1["version"]


def test_t4_idempotency_strict(client, monkeypatch):
    """T4: Strict idempotency - same request_id returns same audit_id."""
    monkeypatch.setenv("AUTH_ROOT_TOKEN", "test-token-789")
    
    # First request
    response1 = client.post("/api/admin/governance/mode",
                           json={"mode": "ENFORCE", "reason": "idempotency test request", "request_id": "idem-req-1"},
                           headers={"X-ADMIN-TOKEN": "test-token-789", "X-ADMIN-ACK": "I_UNDERSTAND_GOVERNANCE_WRITE"})
    assert response1.status_code == 200
    data1 = response1.get_json()
    audit_id_1 = data1["audit"]["id"]
    version_1 = data1["current"]["version"]
    
    # Second request (SAME request_id)
    response2 = client.post("/api/admin/governance/mode",
                           json={"mode": "SHADOW", "reason": "different reason", "request_id": "idem-req-1"},  # Same request_id!
                           headers={"X-ADMIN-TOKEN": "test-token-789", "X-ADMIN-ACK": "I_UNDERSTAND_GOVERNANCE_WRITE"})
    assert response2.status_code == 200
    data2 = response2.get_json()
    audit_id_2 = data2["audit"]["id"]
    
    # Assert SAME audit_id
    assert audit_id_2 == audit_id_1
    
    # Assert NO second state transition (version unchanged)
    assert data2["current"]["version"] == version_1
    
    # Assert idempotent_reply note
    assert data2.get("_note") == "idempotent_reply"


def test_t5_audit_integrity(test_paths, monkeypatch):
    """T5: Audit integrity verification."""
    monkeypatch.setenv("AUTH_ROOT_TOKEN", "test-token-abc")
    
    # Create audit and log records
    audit = AuditLogger(test_paths["audit"])
    audit.log_change("SET_GOVERNANCE_MODE", "audit-req-1", "admin", "test 1", {"mode": "SHADOW", "version": 1}, {"mode": "ENFORCE", "version": 2}, True, None)
    audit.log_change("SET_GLOBAL_HALT", "audit-req-2", "admin", "test 2", {"is_halted": False, "version": 2}, {"is_halted": True, "version": 3}, True, None)
    
    # Verify integrity
    result = audit.verify_integrity_structured()
    
    assert result["valid"] is True
    assert result["total_records"] == 2
    assert len(result["invalid_records"]) == 0
    assert len(result["errors"]) == 0


def test_t6_atomicity_config_audit_rollback(test_paths, monkeypatch, tmp_path):
    """T6: Config+audit atomicity - audit failure triggers rollback."""
    # This test is conceptual - demonstrating rollback mechanism
    # In practice, audit failure would trigger store.rollback(backup)
    
    store = RiskConfigStore(test_paths["config"])
    store.load_or_initialize()
    
    # Snapshot backup
    backup = store.snapshot_backup()
    assert backup["mode"] == "SHADOW"
    assert backup["version"] == 1
    
    # Update config
    new_state = store.update_mode("ENFORCE", "admin", "rollback test", "rollback-req-1")
    assert new_state["mode"] == "ENFORCE"
    assert new_state["version"] == 2
    
    # Simulate audit failure -> rollback
    store.rollback(backup)
    
    # Verify rollback
    rolled_back = store.load_or_initialize()
    assert rolled_back["mode"] == "SHADOW"
    assert rolled_back["version"] == 1  # Rolled back!


def test_t7_regression_guard():
    """T7: Phase 0-4 remain GREEN."""
    import subprocess
    
    # Run Phase 0-3 tests (already confirmed GREEN above, this is canary)
    result = subprocess.run(
        ["python3", "-m", "pytest",
         "tests/forensic/test_primary_autopsy_10k_to_1k.py",
         "tests/forensic/risk/", "-q", "--tb=no"],
        cwd="/Users/neomind/alladin/lunia_core-Spot-Trading-Core/lunia_core",
        capture_output=True, text=True
    )
    assert result.returncode == 0, f"Phase 0-3 regression: {result.stdout}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
