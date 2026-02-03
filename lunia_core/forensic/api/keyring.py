"""Keyring & Rotation State (PHASE 7 - ZERO-DOWNTIME KEY ROTATION)

Dual-token window (CURRENT + NEXT) with fail-closed rotation state.
"""
import os
import json
import hmac
import hashlib
import threading
import fcntl
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from contextlib import contextmanager
from enum import Enum


class Role(Enum):
    """Access control roles (Phase 6 compatibility)."""
    ROOT = "ROOT"
    RISK = "RISK"
    AUDITOR = "AUDITOR"


class RotationState:
    """Manages rotation state with atomic persistence."""
    
    def __init__(self, state_path: str = "data/auth_rotation_state.json"):
        self.state_path = Path(state_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.state_path.parent / "auth_rotation.lock"
        self._lock = threading.RLock()
        self._cached_state: Optional[Dict[str, Any]] = None
    
    @contextmanager
    def _file_lock(self):
        """Cross-process file lock."""
        with open(self.lock_path, 'w') as lock_fd:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
    
    def load_or_initialize(self) -> Dict[str, Any]:
        """Load rotation state or create default."""
        with self._lock, self._file_lock():
            if not self.state_path.exists():
                default = {
                    "version": 1,
                    "updated_at": datetime.utcnow().isoformat() + "Z",
                    "enabled_next_roles": [],  # Empty = NEXT disabled for all
                    "note": "Initial state"
                }
                self._atomic_write(default)
                self._cached_state = default
                return default
            
            with open(self.state_path, 'r') as f:
                state = json.load(f)
            
            self._cached_state = state
            return state
    
    def enable_next_for_roles(self, roles: List[str], reason: str) -> Dict[str, Any]:
        """Enable NEXT token acceptance for specified roles."""
        with self._lock, self._file_lock():
            current = self.load_or_initialize()
            
            new_state = {
                "version": current["version"] + 1,
                "updated_at": datetime.utcnow().isoformat() + "Z",
                "enabled_next_roles": sorted(list(set(roles))),  # Dedup, sort for determinism
                "note": reason[:500]
            }
            
            self._atomic_write(new_state)
            self._cached_state = new_state
            return new_state
    
    def get_enabled_next_roles(self) -> List[str]:
        """Get list of roles with NEXT enabled."""
        state = self.load_or_initialize()
        return state.get("enabled_next_roles", [])
    
    def _atomic_write(self, state: Dict[str, Any]):
        """Atomic write with fsync (Phase 5.1 pattern)."""
        fd, temp_path = tempfile.mkstemp(
            dir=str(self.state_path.parent),
            prefix=f".{self.state_path.name}.",
            suffix=".tmp"
        )
        
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(state, f, indent=2, sort_keys=True)
                f.flush()
                os.fsync(f.fileno())
            
            os.rename(temp_path, self.state_path)
            
            try:
                dir_fd = os.open(self.state_path.parent, os.O_RDONLY)
                os.fsync(dir_fd)
                os.close(dir_fd)
            except (OSError, AttributeError):
                pass
        except Exception as e:
            try:
                os.unlink(temp_path)
            except:
                pass
            raise RuntimeError(f"[ROTATION_STATE_ERROR] Write failed: {e}")


class Keyring:
    """Token resolver with CURRENT+NEXT dual window support."""
    
    def __init__(self, rotation_state: RotationState):
        self.rotation_state = rotation_state
    
    def detect_role(self, provided_token: str) -> Optional[Role]:
        """Detect role from token with CURRENT+NEXT support.
        
        Rules:
            - CURRENT token always accepted (if env var exists)
            - NEXT token accepted only if role in enabled_next_roles
            - ROOT supersedes all roles
            - Constant-time comparison only
            - Fail-closed: missing env var => role unavailable
        
        Returns:
            Role if valid, None otherwise
        """
        if not provided_token:
            return None
        
        # Get enabled_next_roles from rotation state
        enabled_next = self.rotation_state.get_enabled_next_roles()
        
        # Check ROOT (CURRENT)
        root_current = os.getenv("AUTH_ROOT_TOKEN", "")
        if root_current and hmac.compare_digest(provided_token, root_current):
            return Role.ROOT
        
        # Check ROOT (NEXT - if enabled)
        if "ROOT" in enabled_next:
            root_next = os.getenv("AUTH_ROOT_TOKEN_NEXT", "")
            if root_next and hmac.compare_digest(provided_token, root_next):
                return Role.ROOT
        
        # Check RISK (CURRENT)
        risk_current = os.getenv("AUTH_RISK_TOKEN", "")
        if risk_current and hmac.compare_digest(provided_token, risk_current):
            return Role.RISK
        
        # Check RISK (NEXT - if enabled)
        if "RISK" in enabled_next:
            risk_next = os.getenv("AUTH_RISK_TOKEN_NEXT", "")
            if risk_next and hmac.compare_digest(provided_token, risk_next):
                return Role.RISK
        
        # Check AUDITOR (CURRENT)
        auditor_current = os.getenv("AUTH_AUDITOR_TOKEN", "")
        if auditor_current and hmac.compare_digest(provided_token, auditor_current):
            return Role.AUDITOR
        
        # Check AUDITOR (NEXT - if enabled)
        if "AUDITOR" in enabled_next:
            auditor_next = os.getenv("AUTH_AUDITOR_TOKEN_NEXT", "")
            if auditor_next and hmac.compare_digest(provided_token, auditor_next):
                return Role.AUDITOR
        
        # No match
        return None
