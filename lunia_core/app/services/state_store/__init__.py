"""
Epoch C.4 — State Store Package

Persistent storage for lifecycle state, idempotency tracking, and circuit breaker state.
Provides SQLite backend with strict schema governance and fail-closed semantics.
"""
from .models import (
    PersistedExitPlanState,
    LifecycleRegistryState,
    IdempotencyRecord,
    CircuitBreakerRecord,
)
from .interfaces import StateStore
from .sqlite_store import SQLiteStateStore

__all__ = [
    "PersistedExitPlanState",
    "LifecycleRegistryState",
    "IdempotencyRecord",
    "CircuitBreakerRecord",
    "StateStore",
    "SQLiteStateStore",
]
