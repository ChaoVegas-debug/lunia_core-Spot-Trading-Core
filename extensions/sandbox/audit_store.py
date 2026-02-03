"""
PHASE 9.2 — AUDIT STORE

Append-only in-memory audit store with deterministic event IDs and integrity hashing.

SPEC IMPROVEMENT:
- AuditEvent is frozen dataclass (reinforces immutability)

GUARANTEES:
- Events are immutable once appended
- Deterministic event_id from event contents
- Integrity hash covers entire store
- Canonical JSON export for evidence packs
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from extensions.sandbox.serialization import canonical_hash, to_canonical_json


@dataclass(frozen=True)
class AuditEvent:
    """
    Immutable audit event.
    
    SPEC IMPROVEMENT: frozen=True enforces immutability.
    """
    event_id: str          # Deterministic hash of event components
    ts_ms: int             # UTC epoch milliseconds
    event_type: str        # "tick_start" | "tick_end" | "intent_generated" | etc.
    correlation_id: str    # Traceability
    run_id: str            # Governance run ID
    
    # Event-specific payload (varies by event_type)
    payload: Dict[str, Any]
    
    # Optional context
    strategy_id: Optional[str] = None
    intent_id: Optional[str] = None
    reject_code: Optional[str] = None
    severity: Optional[str] = None


class AuditStore:
    """
    Append-only in-memory audit store (MVP).
    
    GUARANTEES:
    - Events cannot be modified after append
    - Events are stored in append order (tick ordering)
    - Integrity hash is deterministic
    """
    
    def __init__(self):
        self._events: List[AuditEvent] = []
        self._event_count = 0
    
    def append(self, event: AuditEvent) -> None:
        """
        Append immutable event to store.
        
        Args:
            event: Frozen AuditEvent to append
        """
        self._events.append(event)
        self._event_count += 1
    
    def get_events(self) -> List[AuditEvent]:
        """
        Get all events (immutable).
        
        Returns:
            List of all events in append order
        """
        return list(self._events)
    
    def get_events_by_type(self, event_type: str) -> List[AuditEvent]:
        """
        Get events filtered by type.
        
        Args:
            event_type: Event type to filter by
            
        Returns:
            List of matching events in append order
        """
        return [e for e in self._events if e.event_type == event_type]
    
    def get_events_by_correlation_id(self, correlation_id: str) -> List[AuditEvent]:
        """
        Get events for a specific correlation ID (tick trace).
        
        Args:
            correlation_id: Correlation ID to filter by
            
        Returns:
            List of matching events in append order
        """
        return [e for e in self._events if e.correlation_id == correlation_id]
    
    def count(self) -> int:
        """Get total event count."""
        return self._event_count
    
    def integrity_hash(self) -> str:
        """
        Generate deterministic integrity hash of entire store.
        
        GUARANTEE: Same events in same order => same hash
        
        Returns:
            SHA256 hash of all events
        """
        # Hash list of event canonical JSONs
        event_jsons = [to_canonical_json(e) for e in self._events]
        combined = "\n".join(event_jsons)
        return canonical_hash(combined)
    
    def export_canonical_json(self) -> str:
        """
        Export store as canonical JSON for evidence packs.
        
        Returns:
            Canonical JSON representation of all events
        """
        return to_canonical_json({
            "event_count": self._event_count,
            "events": self._events,
            "integrity_hash": self.integrity_hash(),
        })
    
    def clear(self) -> None:
        """Clear all events (for testing only)."""
        self._events.clear()
        self._event_count = 0


def create_audit_event(
    ts_ms: int,
    event_type: str,
    correlation_id: str,
    run_id: str,
    payload: Dict[str, Any],
    strategy_id: Optional[str] = None,
    intent_id: Optional[str] = None,
    reject_code: Optional[str] = None,
    severity: Optional[str] = None,
) -> AuditEvent:
    """
    Create audit event with deterministic event_id.
    
    GUARANTEE: Same inputs => same event_id
    
    Args:
        ts_ms: Timestamp in milliseconds
        event_type: Type of event
        correlation_id: Correlation ID for traceability
        run_id: Governance run ID
        payload: Event-specific data
        strategy_id: Optional strategy identifier
        intent_id: Optional intent identifier
        reject_code: Optional rejection code
        severity: Optional severity level
        
    Returns:
        Immutable AuditEvent with deterministic event_id
    """
    # Generate deterministic event_id from components
    components = {
        "ts_ms": ts_ms,
        "event_type": event_type,
        "correlation_id": correlation_id,
        "run_id": run_id,
        "payload": payload,
        "strategy_id": strategy_id,
        "intent_id": intent_id,
        "reject_code": reject_code,
        "severity": severity,
    }
    event_id = canonical_hash(components)[:16]  # 16-char hex prefix
    
    return AuditEvent(
        event_id=event_id,
        ts_ms=ts_ms,
        event_type=event_type,
        correlation_id=correlation_id,
        run_id=run_id,
        payload=payload,
        strategy_id=strategy_id,
        intent_id=intent_id,
        reject_code=reject_code,
        severity=severity,
    )
