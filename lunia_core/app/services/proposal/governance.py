"""
EPOCH B: Governance Validator for Proposals
Fail-closed approval validation
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from ...core.state import get_state as get_runtime_state


class GovernanceVetoError(Exception):
    """Raised when governance blocks an action"""
    def __init__(self, reason: str, code: str = "GOVERNANCE_VETO"):
        self.reason = reason
        self.code = code
        super().__init__(reason)


class ProposalGovernanceValidator:
    """
    Validates governance state for proposal operations
    FAIL-CLOSED: Missing data = block
    """
    
    @staticmethod
    def validate_approval(actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Validate governance state for proposal approval
        
        Returns governance snapshot if valid
        Raises GovernanceVetoError if blocked
        
        FAIL-CLOSED CHECKS:
        - global_stop must be False
        - system_mode must not be STOP
        - airlock_status must be ARMED
        - data_freshness must be FRESH (if run_mode == real)
        - human actor required
        """
        state = get_runtime_state()
        
        # Capture snapshot
        snapshot = ProposalGovernanceValidator._capture_snapshot(state)
        
        # FAIL-CLOSED: global_stop
        if state.get("global_stop", True):  # default True = fail-closed
            raise GovernanceVetoError(
                "Approval blocked: Global emergency stop active",
                code="GLOBAL_STOP_ACTIVE"
            )
        
        # FAIL-CLOSED: system_mode
        system_mode = state.get("system_mode", "STOP")  # default STOP = fail-closed
        if system_mode == "STOP":
            raise GovernanceVetoError(
                "Approval blocked: System in STOP mode",
                code="SYSTEM_MODE_STOP"
            )
        
        # FAIL-CLOSED: airlock_status
        airlock_status = state.get("airlock_status", "NOT_READY")  # default NOT_READY = fail-closed
        if airlock_status != "ARMED":
            raise GovernanceVetoError(
                f"Approval blocked: Airlock status is {airlock_status}, must be ARMED",
                code="AIRLOCK_NOT_ARMED"
            )
        
        # FAIL-CLOSED: run_mode + data_freshness
        run_state = state.get("run_state") or {}
        run_mode = run_state.get("run_mode", "dry")  # default dry = safe
        
        if run_mode == "real":
            # Real mode requires FRESH data
            freshness = ProposalGovernanceValidator._compute_freshness(state)
            if freshness != "FRESH":
                raise GovernanceVetoError(
                    f"Approval blocked: Data freshness is {freshness}, real approvals require FRESH data",
                    code="DATA_NOT_FRESH"
                )
        
        # FAIL-CLOSED: human actor requirement
        if not actor or not actor.get("user_id"):
            raise GovernanceVetoError(
                "Approval blocked: Human actor required for approval",
                code="NO_HUMAN_ACTOR"
            )
        
        # Drift check (warning, not block)
        drift_status = state.get("drift_status")
        if drift_status and drift_status != "NONE":
            # Log warning but don't block
            import logging
            logging.warning(f"Approval proceeding with drift detected: {drift_status}")
        
        return snapshot
    
    @staticmethod
    def _capture_snapshot(state: Dict[str, Any]) -> Dict[str, Any]:
        """Capture governance snapshot for audit"""
        run_state = state.get("run_state") or {}
        
        snapshot = {
            "global_stop": state.get("global_stop", True),
            "system_mode": state.get("system_mode", "STOP"),
            "run_mode": run_state.get("run_mode", "dry"),
            "airlock_status": state.get("airlock_status", "NOT_READY"),
            "live_allowed": state.get("live_allowed", False),
            "tier": state.get("tier", "UNKNOWN"),
            "data_freshness_state": ProposalGovernanceValidator._compute_freshness(state),
            "data_freshness_metrics": ProposalGovernanceValidator._compute_freshness_metrics(state),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Optional fields
        if state.get("veto_reason"):
            snapshot["veto_reason"] = state["veto_reason"]
        if state.get("drift_status"):
            snapshot["drift_status"] = state["drift_status"]
        
        return snapshot
    
    @staticmethod
    def _compute_freshness(state: Dict[str, Any]) -> str:
        """Compute data freshness state"""
        # Try to get last update timestamp
        last_updated = state.get("last_updated") or state.get("updated_at")
        
        if not last_updated:
            return "OFFLINE"  # No timestamp = offline
        
        try:
            last_update_dt = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
            age_seconds = (datetime.utcnow() - last_update_dt.replace(tzinfo=None)).total_seconds()
            
            if age_seconds > 30:
                return "DEGRADED"  # >30s old
            elif age_seconds > 10:
                return "STALE"  # >10s old
            else:
                return "FRESH"  # <=10s old
        except Exception:
            return "OFFLINE"  # Parse error = offline
    
    @staticmethod
    def _compute_freshness_metrics(state: Dict[str, Any]) -> Dict[str, Any]:
        """Compute freshness metrics"""
        last_updated = state.get("last_updated") or state.get("updated_at")
        
        if not last_updated:
            return {"ops_age_ms": None, "health_age_ms": None}
        
        try:
            last_update_dt = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
            age_ms = int((datetime.utcnow() - last_update_dt.replace(tzinfo=None)).total_seconds() * 1000)
            return {"ops_age_ms": age_ms, "health_age_ms": 0}
        except Exception:
            return {"ops_age_ms": None, "health_age_ms": None}
    
    @staticmethod
    def capture_creation_snapshot() -> Dict[str, Any]:
        """Capture governance snapshot for proposal creation"""
        state = get_runtime_state()
        return ProposalGovernanceValidator._capture_snapshot(state)
