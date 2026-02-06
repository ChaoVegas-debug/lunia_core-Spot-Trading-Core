"""
Epoch C.4 — State Store Interface

Protocol defining the state store contract.
"""
from typing import Protocol, Dict, Any, List, Optional

from .models import (
    PersistedExitPlanState,
    LifecycleRegistryState,
    IdempotencyRecord,
    CircuitBreakerRecord,
)


class StateStore(Protocol):
    """
    Protocol for persistent state storage.
    
    Defines contract for storing lifecycle state, idempotency keys,
    and circuit breaker state with strict schema governance.
    """
    
    def init(self) -> None:
        """
        Initialize storage backend.
        
        Creates schema if needed, validates version.
        Raises on schema mismatch.
        """
        ...
    
    def health(self) -> Dict[str, Any]:
        """
        Check storage health.
        
        Returns:
            Dict with status, schema version, record counts, etc.
        """
        ...
    
    def load_registry(self, as_of_ms: int) -> LifecycleRegistryState:
        """
        Load complete lifecycle registry state.
        
        Args:
            as_of_ms: Timestamp for loading state
        
        Returns:
            Complete registry with all active exit plans
        """
        ...
    
    def upsert_exit_plan(self, state: PersistedExitPlanState) -> None:
        """
        Insert or update exit plan state.
        
        Args:
            state: Exit plan state to persist
        """
        ...
    
    def mark_closed(self, position_id: str, reason: str, closed_at_ms: int) -> None:
        """
        Mark exit plan as closed.
        
        Args:
            position_id: Position identifier
            reason: Close reason
            closed_at_ms: Close timestamp
        """
        ...
    
    def list_active(self, as_of_ms: int) -> List[PersistedExitPlanState]:
        """
        List all active exit plans.
        
        Args:
            as_of_ms: Timestamp for filtering active plans
        
        Returns:
            List of active exit plan states
        """
        ...
    
    def reserve_idempotency(
        self, key: str, payload_hash: str, now_ms: int, ttl_ms: int
    ) -> bool:
        """
        Reserve idempotency key.
        
        Args:
            key: Idempotency key
            payload_hash: Hash of payload
            now_ms: Current timestamp
            ttl_ms: Time-to-live
        
        Returns:
            True if reserved (new), False if already exists
        """
        ...
    
    def commit_idempotency(self, key: str, now_ms: int) -> None:
        """
        Commit idempotency key after successful execution.
        
        Args:
            key: Idempotency key
            now_ms: Commit timestamp
        """
        ...
    
    def purge_idempotency(self, now_ms: int) -> int:
        """
        Purge expired idempotency keys.
        
        Args:
            now_ms: Current timestamp
        
        Returns:
            Number of keys purged
        """
        ...
    
    def load_circuit_breaker(
        self, adapter_name: str, symbol: str
    ) -> Optional[CircuitBreakerRecord]:
        """
        Load circuit breaker state.
        
        Args:
            adapter_name: Exchange adapter name
            symbol: Trading symbol
        
        Returns:
            Circuit breaker record or None
        """
        ...
    
    def save_circuit_breaker(self, record: CircuitBreakerRecord) -> None:
        """
        Save circuit breaker state.
        
        Args:
            record: Circuit breaker record
        """
        ...
