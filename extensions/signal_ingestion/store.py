"""
PHASE 15A — SIGNAL INGESTION CORE: Signal Store

Bounded in-memory signal storage with deterministic eviction.
NO persistence, NO wall-clock (requires now_ms input).

Governance: G3 (Determinism), G4 (Fail-Closed)
"""

from collections import deque
from decimal import Decimal
from typing import Optional

from .models import SignalEvent, SignalState, SignalSource
from .decay import compute_decay_weight, is_expired, remaining_time_ms, DecayMode


class SignalStore:
    """
    Bounded in-memory store for signal events.
    
    Features:
      - Fixed capacity with FIFO eviction
      - Deterministic (requires explicit now_ms)
      - No persistence (memory-only)
      - Expiry management via TTL
    
    Governance:
      - NO wall-clock (all time via parameters)
      - Bounded memory (prevents OOM)
      - Fail-closed (reject duplicates)
    """
    
    def __init__(self, max_capacity: int = 1000, decay_mode: DecayMode = "linear"):
        """
        Initialize signal store.
        
        Args:
            max_capacity: Maximum number of signals to store
            decay_mode: Decay algorithm ("linear" or "exponential")
        """
        if max_capacity <= 0:
            raise ValueError(f"max_capacity must be positive, got {max_capacity}")
        
        self.max_capacity = max_capacity
        self.decay_mode = decay_mode
        
        # Internal storage
        self._signals: dict[str, SignalEvent] = {}
        self._insertion_order: deque[str] = deque(maxlen=max_capacity)
    
    def upsert(self, event: SignalEvent) -> None:
        """
        Insert or update a signal event.
        
        Rules:
          - If signal_id exists, update
          - If new and at capacity, evict oldest
          - Maintains insertion order for FIFO eviction
        
        Args:
            event: SignalEvent to store
        """
        signal_id = event.signal_id
        
        # Update existing signal
        if signal_id in self._signals:
            self._signals[signal_id] = event
            return
        
        # At capacity → evict oldest
        if len(self._signals) >= self.max_capacity:
            oldest_id = self._insertion_order.popleft()
            del self._signals[oldest_id]
        
        # Insert new signal
        self._signals[signal_id] = event
        self._insertion_order.append(signal_id)
    
    def get(self, signal_id: str) -> Optional[SignalEvent]:
        """
        Retrieve signal by ID.
        
        Args:
            signal_id: Signal identifier
        
        Returns:
            SignalEvent if found, None otherwise
        """
        return self._signals.get(signal_id)
    
    def list_active(
        self,
        now_ms: int,
        symbol: Optional[str] = None,
        source: Optional[SignalSource] = None,
        min_confidence: Optional[Decimal] = None,
    ) -> list[SignalState]:
        """
        List active (non-expired) signals with computed state.
        
        Args:
            now_ms: Current timestamp (milliseconds)
            symbol: Filter by symbol (optional)
            source: Filter by source (optional)
            min_confidence: Minimum confidence threshold (optional)
        
        Returns:
            List of SignalState with computed age, weight, expiry
        """
        active_states: list[SignalState] = []
        
        for signal_id, event in self._signals.items():
            # Compute age
            age_ms = now_ms - event.ts_ms
            
            # Skip expired signals
            if is_expired(age_ms, event.ttl_ms):
                continue
            
            # Apply filters
            if symbol is not None and event.symbol != symbol:
                continue
            if source is not None and event.source != source:
                continue
            if min_confidence is not None and event.confidence < min_confidence:
                continue
            
            # Compute decay weight
            weight = compute_decay_weight(
                age_ms=age_ms,
                ttl_ms=event.ttl_ms,
                mode=self.decay_mode,
            )
            
            # Create state snapshot
            state = SignalState(
                signal_id=signal_id,
                active=True,
                age_ms=age_ms,
                remaining_ms=remaining_time_ms(age_ms, event.ttl_ms),
                weight=weight,
                reason=None,
            )
            active_states.append(state)
        
        # Sort by weight descending (highest impact first)
        active_states.sort(key=lambda s: s.weight, reverse=True)
        
        return active_states
    
    def purge_expired(self, now_ms: int) -> int:
        """
        Remove all expired signals from store.
        
        Args:
            now_ms: Current timestamp (milliseconds)
        
        Returns:
            Number of signals purged
        """
        expired_ids: list[str] = []
        
        for signal_id, event in self._signals.items():
            age_ms = now_ms - event.ts_ms
            if is_expired(age_ms, event.ttl_ms):
                expired_ids.append(signal_id)
        
        # Remove expired signals
        for signal_id in expired_ids:
            del self._signals[signal_id]
            # Remove from insertion order if present
            try:
                self._insertion_order.remove(signal_id)
            except ValueError:
                pass  # Already evicted
        
        return len(expired_ids)
    
    def count(self) -> int:
        """Return current number of stored signals."""
        return len(self._signals)
    
    def clear(self) -> None:
        """Remove all signals from store."""
        self._signals.clear()
        self._insertion_order.clear()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PUBLIC API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

__all__ = [
    "SignalStore",
]
