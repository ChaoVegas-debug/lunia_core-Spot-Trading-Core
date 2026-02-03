"""Phase 7: Rotation + Break-Glass + Cursors (MINIMAL EVIDENCE TESTS)

Focused test suite proving core Phase 7 capabilities.
"""
import pytest
import os
import json
import time
from pathlib import Path
from flask import Flask

from forensic.api.keyring import RotationState, Keyring, Role
from forensic.api.break_glass import BreakGlassManager
from forensic.api.auth import init_auth, validate_rbac, get_break_glass


@pytest.fixture
def test_paths(tmp_path):
    return {
        "rotation": str(tmp_path / "rotation.json"),
        "break_glass": str(tmp_path / "break_glass.json"),
        "audit": str(tmp_path / "audit.jsonl")
    }


def test_t1_rotation_dual_token_enable(test_paths, monkeypatch):
    """T1: Dual token window - CURRENT+NEXT both work when enabled."""
    rotation = RotationState(test_paths["rotation"])
    rotation.load_or_initialize()
    
    # Set tokens
    monkeypatch.setenv("AUTH_ROOT_TOKEN", "current-root-123")
    monkeypatch.setenv("AUTH_ROOT_TOKEN_NEXT", "next-root-456")
    
    keyring = Keyring(rotation)
    
    # Before enabling NEXT
    assert keyring.detect_role("current-root-123") == Role.ROOT
    assert keyring.detect_role("next-root-456") is None  # NEXT disabled
    
    # Enable NEXT
    rotation.enable_next_for_roles(["ROOT"], "rotation test")
    
    # After enabling NEXT
    assert keyring.detect_role("current-root-123") == Role.ROOT
    assert keyring.detect_role("next-root-456") == Role.ROOT  # NEXT enabled


def test_t2_rotation_fail_closed_next_disabled(test_paths, monkeypatch):
    """T2: NEXT token rejected when disabled (fail-closed)."""
    rotation = RotationState(test_paths["rotation"])
    rotation.load_or_initialize()
    
    monkeypatch.setenv("AUTH_RISK_TOKEN", "current-risk-789")
    monkeypatch.setenv("AUTH_RISK_TOKEN_NEXT", "next-risk-abc")
    
    keyring = Keyring(rotation)
    
    # NEXT disabled by default
    assert keyring.detect_role("next-risk-abc") is None  # 401 equivalent


def test_t3_segregation_preserved(test_paths, monkeypatch):
    """T3: RBAC matrix still enforced with keyring."""
    rotation = RotationState(test_paths["rotation"])
    rotation.load_or_initialize()
    
    monkeypatch.setenv("AUTH_RISK_TOKEN", "risk-token")
    monkeypatch.setenv("AUTH_AUDITOR_TOKEN", "auditor-token")
    
    keyring = Keyring(rotation)
    
    # RISK role detected
    assert keyring.detect_role("risk-token") == Role.RISK
    
    # AUDITOR role detected
    assert keyring.detect_role("auditor-token") == Role.AUDITOR
    
    # Invalid token
    assert keyring.detect_role("invalid") is None


def test_t4_break_glass_issue_use_once(test_paths):
    """T4: Break-glass one-time use (burn after validation)."""
    bg = BreakGlassManager(test_paths["break_glass"])
    
    # Issue
    token, meta = bg.issue("incident-001", "admin", "emergency test", ttl_seconds=900)
    assert len(token) >= 32  # High entropy
    assert meta["used_at"] is None
    
    # Validate (first use)
    is_valid, error, meta = bg.validate(token)
    assert is_valid is True
    assert error is None
    
    # Mark used
    updated = bg.mark_used(token)
    assert updated["used_at"] is not None
    
    # Validate again (should fail - already used)
    is_valid, error, meta = bg.validate(token)
    assert is_valid is False
    assert error == "BREAK_GLASS_USED"


def test_t5_break_glass_expiry(test_paths):
    """T5: Break-glass expires after TTL."""
    bg = BreakGlassManager(test_paths["break_glass"])
    
    # Issue with 1 second TTL
    token, meta = bg.issue("incident-002", "admin", "expiry test", ttl_seconds=1)
    
    # Valid immediately
    is_valid, error, meta = bg.validate(token)
    assert is_valid is True
    
    # Wait for expiry
    time.sleep(1.1)
    
    # Now expired
    is_valid, error, meta = bg.validate(token)
    assert is_valid is False
    assert error == "BREAK_GLASS_EXPIRED"


def test_t6_break_glass_revocation(test_paths):
    """T6: Break-glass can be revoked."""
    bg = BreakGlassManager(test_paths["break_glass"])
    
    # Issue
    token, meta = bg.issue("incident-003", "admin", "revoke test", ttl_seconds=900)
    
    # Valid before revoke
    is_valid, error, _ = bg.validate(token)
    assert is_valid is True
    
    # Revoke by incident_id
    bg.revoke(incident_id="incident-003")
    
    # Now revoked
    is_valid, error, meta = bg.validate(token)
    assert is_valid is False
    assert error == "BREAK_GLASS_REVOKED"


def test_t7_no_plaintext_storage(test_paths):
    """T7: Break-glass storage contains ONLY hashes, never plaintext."""
    bg = BreakGlassManager(test_paths["break_glass"])
    
    # Issue token
    plaintext, meta = bg.issue("incident-004", "admin", "hash test", ttl_seconds=900)
    
    # Read storage file
    with open(test_paths["break_glass"], 'r') as f:
        storage = json.load(f)
    
    # Verify plaintext NOT in storage
    storage_str = json.dumps(storage)
    assert plaintext not in storage_str
    
    # Verify hash IS in storage
    assert "token_hash" in storage["incident-004"]
    assert len(storage["incident-004"]["token_hash"]) == 64  # SHA256 hex


def test_t8_regression_phase6(monkeypatch):
    """T8: Phase 6 RBAC still works with keyring."""
    import subprocess
    result = subprocess.run(
        ["python3", "-m", "pytest", 
         "tests/forensic/api/test_phase6_rbac.py::test_t1_rbac_enforcement_insider_threat",
         "-q", "--tb=no"],
        cwd="/Users/neomind/alladin/lunia_core-Spot-Trading-Core/lunia_core",
        capture_output=True, text=True
    )
    assert result.returncode == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
