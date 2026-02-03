"""
PHASE 10 — PROPOSAL SYSTEM: Proposal Audit Store

Isolated audit trail for proposal lifecycle events.

ISOLATION: Independent from Phase 9.2 AuditStore (different domain).
DETERMINISM: event_id generated via SHA256 of canonical event fields.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from collections import OrderedDict

from extensions.proposals.types import ProposalStatus
from extensions.proposals.canonical import to_canonical_json, sha16_from_fields


# ────────────────────────────────────────────────────────────────────────────────
# AUDIT EVENT
# ────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ProposalAuditEvent:
    """
    Immutable proposal audit event.
    
    Records state changes and lifecycle transitions for proposals.
    """
    event_id: str  # 16-hex deterministic (sha256 of core fields)
    proposal_id: str
    ts_ms: int
    actor: str  # "USER", "RISK_ENGINE", "SYSTEM", etc.
    event_type: str  # "proposal_created", "status_changed", "synced_executed", etc.
    old_status: Optional[ProposalStatus]
    new_status: Optional[ProposalStatus]
    reason: Optional[str]
    payload: Dict[str, Any]  # Additional context (JSON-safe)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "event_id": self.event_id,
            "proposal_id": self.proposal_id,
            "ts_ms": self.ts_ms,
            "actor": self.actor,
            "event_type": self.event_type,
            "old_status": self.old_status.value if self.old_status else None,
            "new_status": self.new_status.value if self.new_status else None,
            "reason": self.reason,
            "payload": self.payload,
        }


# ────────────────────────────────────────────────────────────────────────────────
# PROPOSAL AUDIT STORE
# ────────────────────────────────────────────────────────────────────────────────


class ProposalAuditStore:
    """
    Append-only in-memory audit store for proposal events.
    
    ISOLATION: Separate from Phase 9.2 AuditStore
    DETERMINISM: Integrity hash over canonical export
    """
    
    def __init__(self):
        """Initialize empty audit store."""
        self._events: List[ProposalAuditEvent] = []
        self._events_by_proposal: Dict[str, List[ProposalAuditEvent]] = {}
    
    def append(self, event: ProposalAuditEvent) -> None:
        """
        Append audit event to store.
        
        Args:
            event: ProposalAuditEvent to append
        """
        self._events.append(event)
        
        # Index by proposal_id for fast lookup
        if event.proposal_id not in self._events_by_proposal:
            self._events_by_proposal[event.proposal_id] = []
        self._events_by_proposal[event.proposal_id].append(event)
    
    def list_for_proposal(self, proposal_id: str) -> List[ProposalAuditEvent]:
        """
        Get all audit events for a specific proposal.
        
        Args:
            proposal_id: Proposal ID to lookup
        
        Returns:
            List of ProposalAuditEvents (chronological order)
        """
        return self._events_by_proposal.get(proposal_id, [])
    
    def export_canonical_json(self) -> str:
        """
        Export all events as canonical JSON.
        
        Returns:
            Canonical JSON string of all events
        """
        events_data = [event.to_dict() for event in self._events]
        return to_canonical_json(events_data)
    
    def integrity_hash(self) -> str:
        """
        Generate deterministic integrity hash over all events.
        
        Returns:
            SHA256 hash (full 64-char hex)
        """
        canonical = self.export_canonical_json()
        import hashlib
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    
    def count(self) -> int:
        """Return total number of events."""
        return len(self._events)


# ────────────────────────────────────────────────────────────────────────────────
# EVENT FACTORY
# ────────────────────────────────────────────────────────────────────────────────


def create_audit_event(
    proposal_id: str,
    ts_ms: int,
    actor: str,
    event_type: str,
    old_status: Optional[ProposalStatus] = None,
    new_status: Optional[ProposalStatus] = None,
    reason: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> ProposalAuditEvent:
    """
    Create proposal audit event with deterministic event_id.
    
    Args:
        proposal_id: Proposal ID
        ts_ms: Timestamp (milliseconds)
        actor: Actor performing action
        event_type: Type of event
        old_status: Previous status (if applicable)
        new_status: New status (if applicable)
        reason: Reason for event (optional)
        payload: Additional context (optional)
    
    Returns:
        ProposalAuditEvent with deterministic event_id
    """
    # Generate deterministic event_id
    id_fields = {
        "proposal_id": proposal_id,
        "ts_ms": ts_ms,
        "actor": actor,
        "event_type": event_type,
        "old_status": old_status.value if old_status else None,
        "new_status": new_status.value if new_status else None,
    }
    event_id = sha16_from_fields(id_fields)
    
    return ProposalAuditEvent(
        event_id=event_id,
        proposal_id=proposal_id,
        ts_ms=ts_ms,
        actor=actor,
        event_type=event_type,
        old_status=old_status,
        new_status=new_status,
        reason=reason,
        payload=payload or {},
    )
