"""
Epoch C: Idempotency Layer

Exactly-once semantics: Same verdict_id → Same result (no duplicate execution).
"""
import logging
from typing import Optional, Dict

from .models import ExecutionResult

logger = logging.getLogger(__name__)


class IdempotencyStore:
    """
    In-memory idempotency cache.
    
    Production: Replace with DB-backed store (Redis/PostgreSQL).
    """
    
    def __init__(self):
        self._cache: Dict[str, ExecutionResult] = {}
    
    def get(self, verdict_id: str) -> Optional[ExecutionResult]:
        """Check if verdict already executed"""
        return self._cache.get(verdict_id)
    
    def store(self, verdict_id: str, result: ExecutionResult) -> None:
        """Store execution result"""
        if verdict_id in self._cache:
            logger.warning(
                f"Idempotency collision: verdict {verdict_id[:8]} already exists. "
                "This should not happen if checks are correct."
            )
        self._cache[verdict_id] = result
        logger.info(f"Stored idempotency key: {verdict_id[:8]}...")
    
    def clear(self) -> None:
        """Clear cache (for testing)"""
        self._cache.clear()
