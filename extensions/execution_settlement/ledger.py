"""
PHASE 14E — EXECUTION SETTLEMENT: Ledger (Append-Only)

Append-only execution ledger with bounded processed-index cache.

CRITICAL RULES:
- Append-only (never mutates historical entries)
- Bounded index (deque + set for O(1) membership)
- Idempotency (has_processed check)
- Deterministic entries
- No wall-clock
"""

from collections import deque
from typing import Dict, Any, Optional, Set

from extensions.genome_dsl.audit_store import AuditStore


# ────────────────────────────────────────────────────────────────────────────────
# EXECUTION LEDGER (APPEND-ONLY)
# ────────────────────────────────────────────────────────────────────────────────

class ExecutionLedger:
    """
    Append-only execution ledger with bounded processed-index cache.
    
    Responsibilities:
    - Record trades to append-only audit store
    - Maintain bounded idempotency index
    - Provide has_processed() check (O(1))
    
    Rules:
    - Never mutates historical entries
    - Bounded memory (deque + set with maxlen)
    - Deterministic entry schema
    """
    
    def __init__(
        self,
        audit_store: AuditStore,
        *,
        max_index: int = 5000,
    ):
        """
        Initialize execution ledger.
        
        Args:
            audit_store: AuditStore (append-only persistence)
            max_index: Max idempotency keys to cache (bounded memory)
        """
        self._audit_store = audit_store
        self._max_index = max_index
        
        # Bounded processed-index cache
        # deque maintains insertion order for eviction
        # set provides O(1) membership check
        self._processed_keys_order: deque = deque(maxlen=max_index)
        self._processed_keys_set: Set[str] = set()
    
    def has_processed(self, idempotency_key: str) -> bool:
        """
        Check if idempotency key has been processed (O(1)).
        
        Args:
            idempotency_key: Idempotency key to check
        
        Returns:
            True if previously processed, False otherwise
        """
        return idempotency_key in self._processed_keys_set
    
    def record_trade(
        self,
        entry: Dict[str, Any],
        *,
        idempotency_key: str,
    ) -> str:
        """
        Record trade to append-only ledger.
        
        Args:
            entry: Ledger entry dict (deterministic schema)
            idempotency_key: Idempotency key (for processed-index)
        
        Returns:
            Ledger reference ID from audit_store
        
        Side Effects:
            - Appends to audit_store
            - Updates processed-index cache
            - May evict oldest key if max_index exceeded
        """
        # Append to ledger (audit_store)
        ledger_entry = {
            "schema_version": "1.0.0",
            "phase": "14E",
            "event": "LEDGER_TRADE_RECORDED",
            "timestamp_ms": entry.get("ts_ms"),
            "symbol": entry.get("symbol"),
            "data": entry,
        }
        
        ledger_ref = self._audit_store.append(ledger_entry)
        
        # Update processed-index cache
        # Check if key already in set (shouldn't happen, but defensive)
        if idempotency_key not in self._processed_keys_set:
            # Add to deque (bounded, auto-evicts oldest if maxlen exceeded)
            self._processed_keys_order.append(idempotency_key)
            
            # Add to set
            self._processed_keys_set.add(idempotency_key)
            
            # If deque evicted (length check), remove from set
            # deque maxlen auto-evicts, but we need to sync set
            if len(self._processed_keys_set) > self._max_index:
                # Find evicted key (not in deque anymore)
                keys_in_deque = set(self._processed_keys_order)
                evicted_keys = self._processed_keys_set - keys_in_deque
                
                # Remove evicted keys from set
                for evicted_key in evicted_keys:
                    self._processed_keys_set.discard(evicted_key)
        
        return ledger_ref
