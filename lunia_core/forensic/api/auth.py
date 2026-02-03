"""Centralized RBAC & Authentication (PHASE 7 - KEYRING + BREAK-GLASS INTEGRATED)

Fail-closed role-based access control with rotation support and emergency access.
"""
import os
from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime
from flask import request

from forensic.api.keyring import Keyring, RotationState, Role
from forensic.api.break_glass import BreakGlassManager


# Global instances
_rotation_state: Optional[RotationState] = None
_keyring: Optional[Keyring] = None
_break_glass: Optional[BreakGlassManager] = None


def init_auth(rotation_state_path: str = "data/auth_rotation_state.json", 
              break_glass_path: str = "data/break_glass.json"):
    """Initialize auth subsystem."""
    global _rotation_state, _keyring, _break_glass
    _rotation_state = RotationState(rotation_state_path)
    _rotation_state.load_or_initialize()
    _keyring = Keyring(_rotation_state)
    _break_glass = BreakGlassManager(break_glass_path)


def get_keyring() -> Keyring:
    if _keyring is None:
        raise RuntimeError("Keyring not initialized")
    return _keyring


def get_break_glass() -> BreakGlassManager:
    if _break_glass is None:
        raise RuntimeError("Break-glass not initialized")
    return _break_glass


@dataclass
class RBACResult:
    """Result of RBAC validation."""
    ok: bool
    status_code: int
    error_code: str
    role: Optional[Role]
    timestamp: str
    message: str = ""
    is_break_glass: bool = False


def validate_rbac(required_roles: List[Role]) -> RBACResult:
    """Validate role-based access control with keyring + break-glass fallback."""
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    provided_token = request.headers.get("X-ADMIN-TOKEN", "")
    
    if not provided_token:
        return RBACResult(
            ok=False, status_code=401, error_code="INVALID_TOKEN",
            role=None, timestamp=timestamp, message="Missing authentication token"
        )
    
    # Try normal keyring authentication
    keyring = get_keyring()
    detected_role = keyring.detect_role(provided_token)
    
    if detected_role:
        # ROOT supersedes all
        if detected_role == Role.ROOT:
            return RBACResult(ok=True, status_code=200, error_code="", role=detected_role, timestamp=timestamp)
        
        # Check authorization
        if detected_role in required_roles:
            return RBACResult(ok=True, status_code=200, error_code="", role=detected_role, timestamp=timestamp)
        
        return RBACResult(
            ok=False, status_code=403, error_code="INSUFFICIENT_ROLE",
            role=detected_role, timestamp=timestamp,
            message=f"Role {detected_role.value} not authorized"
        )
    
    # Fallback: try break-glass
    bg = get_break_glass()
    is_valid, error_code, metadata = bg.validate(provided_token)
    
    if is_valid:
        # Break-glass acts as ROOT
        return RBACResult(
            ok=True, status_code=200, error_code="", role=Role.ROOT,
            timestamp=timestamp, is_break_glass=True
        )
    
    if error_code:
        # Break-glass specific error
        return RBACResult(
            ok=False, status_code=409, error_code=error_code,
            role=None, timestamp=timestamp, message=f"Break-glass: {error_code}"
        )
    
    # Invalid token
    return RBACResult(
        ok=False, status_code=401, error_code="INVALID_TOKEN",
        role=None, timestamp=timestamp, message="Invalid authentication token"
    )


def require_ack_for_write() -> RBACResult:
    """Validate X-ADMIN-ACK header for write operations."""
    timestamp = datetime.utcnow().isoformat() + "Z"
    ack = request.headers.get("X-ADMIN-ACK", "")
    
    if not ack:
        return RBACResult(
            ok=False, status_code=403, error_code="MISSING_ADMIN_ACK",
            role=None, timestamp=timestamp, message="Missing X-ADMIN-ACK header"
        )
    
    if ack != "I_UNDERSTAND_GOVERNANCE_WRITE":
        return RBACResult(
            ok=False, status_code=403, error_code="INVALID_ADMIN_ACK",
            role=None, timestamp=timestamp, message="Invalid X-ADMIN-ACK value"
        )
    
    return RBACResult(ok=True, status_code=200, error_code="", role=None, timestamp=timestamp)


def make_error_payload(error_code: str, message: str, request_id: Optional[str] = None) -> dict:
    """Create standardized error response payload."""
    return {
        "status": "error",
        "error_code": error_code,
        "message": message,
        "details": {"request_id": request_id},
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
