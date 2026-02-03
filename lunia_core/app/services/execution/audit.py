"""
EPOCH C: Execution Audit Service
Append-only audit events for all execution transitions
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from .models import ExecutionAuditEvent


def emit_execution_audit(
    session: Session,
    event_type: str,
    intent_id: str,
    plan_id: Optional[str] = None,
    order_execution_id: Optional[str] = None,
    worker_id: Optional[str] = None,
    reason_codes: Optional[List[str]] = None,
    plan_hash: Optional[str] = None,
    intent_hash: Optional[str] = None,
    exchange_response: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> ExecutionAuditEvent:
    """
    Emit execution audit event (append-only)
    
    Args:
        session: SQLAlchemy session
        event_type: Event type (INTENT_VALIDATED, ORDER_SUBMITTED, etc.)
        intent_id: Execution intent ID
        plan_id: Order plan ID (if applicable)
        order_execution_id: Order execution ID (if applicable)
        worker_id: Worker ID (if applicable)
        reason_codes: Machine-readable reason codes
        plan_hash: Plan hash (deterministicverification)
        intent_hash: Intent hash (deterministic verification)
        exchange_response: Sanitized exchange response
        metadata: Additional metadata
    
    Returns:
        Created ExecutionAuditEvent
    """
    event = ExecutionAuditEvent(
        event_type=event_type,
        intent_id=intent_id,
        order_plan_id=plan_id,
        order_execution_id=order_execution_id,
        worker_id=worker_id,
        reason_codes=reason_codes or [],
        plan_hash=plan_hash,
        intent_hash=intent_hash,
        exchange_response=sanitize_exchange_response(exchange_response) if exchange_response else None,
        metadata=metadata or {},
        timestamp=datetime.now(timezone.utc)
    )
    
    session.add(event)
    session.flush()  # Get ID immediately
    
    return event


def sanitize_exchange_response(response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize exchange response for audit storage
    
    Remove sensitive fields (API keys, secrets) and limit size
    
    Args:
        response: Raw exchange response
    
    Returns:
        Sanitized response
    """
    # Fields to remove (security)
    sensitive_fields = {"api_key", "secret", "signature", "recvWindow", "timestamp_signature"}
    
    # Recursive sanitization
    def _sanitize(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {
                k: _sanitize(v)
                for k, v in obj.items()
                if k.lower() not in sensitive_fields
            }
        elif isinstance(obj, list):
            return [_sanitize(item) for item in obj]
        else:
            return obj
    
    sanitized = _sanitize(response)
    
    # Limit size (max 10KB)
    import json
    json_str = json.dumps(sanitized)
    if len(json_str) > 10000:
        return {
            "truncated": True,
            "size_bytes": len(json_str),
            "preview": json_str[:5000]
        }
    
    return sanitized


# Event type constants (for consistency)
class AuditEventType:
    """Execution audit event types"""
    INTENT_VALIDATED = "INTENT_VALIDATED"
    INTENT_BLOCKED = "INTENT_BLOCKED"
    INTENT_QUEUED = "INTENT_QUEUED"
    ORDERPLAN_CREATED = "ORDERPLAN_CREATED"
    ORDER_SUBMIT_ATTEMPTED = "ORDER_SUBMIT_ATTEMPTED"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_SUBMITTED_SIMULATION = "ORDER_SUBMITTED_SIMULATION"  # DRY mode
    ORDER_REJECTED = "ORDER_REJECTED"
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_FILLED_RECONCILED = "ORDER_FILLED_RECONCILED"
    ORDER_PARTIALLY_FILLED = "ORDER_PARTIALLY_FILLED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    ORPHAN_POSITION_DETECTED = "ORPHAN_POSITION_DETECTED"
    ORPHAN_POSITION_DETECTED_SIMULATION = "ORPHAN_POSITION_DETECTED_SIMULATION"  # DRY mode
    EMERGENCY_CLOSE_SUBMITTED = "EMERGENCY_CLOSE_SUBMITTED"
    EMERGENCY_CLOSE_BLOCKED = "EMERGENCY_CLOSE_BLOCKED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    EXECUTION_ABORTED = "EXECUTION_ABORTED"
    GLOBAL_STOP_ABORT = "GLOBAL_STOP_ABORT"
    RECOVERY_RECONCILIATION = "RECOVERY_RECONCILIATION"
    RECONCILIATION_ORDER_NOT_FOUND = "RECONCILIATION_ORDER_NOT_FOUND"
