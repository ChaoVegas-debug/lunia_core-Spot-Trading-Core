"""
Epoch C.1: Retry Guard

Deterministic retry logic for network errors ONLY.

RETRY RULES (NON-NEGOTIABLE):
1. ONLY retry on NETWORK_ERROR
2. NO retry on exchange rejections (INSUFFICIENT_FUNDS, INVALID_SYMBOL, etc.)
3. Max 2 retries (3 total attempts)
4. Exponential backoff: 1s, 2s (deterministic)
5. All attempts MUST be journaled
"""
import time
import logging
from typing import Callable, Optional

from ..models import OrderPlan, ExecutionResult

logger = logging.getLogger(__name__)


class RetryGuard:
    """
    Deterministic retry guard for network errors.
    
    CRITICAL: Only retries transient network errors, never exchange rejections.
    """
    
    # Errors eligible for retry
    RETRIABLE_ERRORS = {"NETWORK_ERROR"}
    
    # Backoff schedule (deterministic)
    BACKOFF_SCHEDULE = [1.0, 2.0]  # Seconds between retries
    
    MAX_RETRIES = 2
    
    def __init__(self, journal_callback: Optional[Callable] = None):
        """
        Args:
            journal_callback: Function to log retry events
                Signature: callback(event_type: str, plan_id: str, detail: str, metadata: dict)
        """
        self.journal_callback = journal_callback
    
    def _should_retry(self, result: ExecutionResult, attempt: int) -> bool:
        """
        Determine if retry is allowed.
        
        Returns True only if:
        - Error code is in RETRIABLE_ERRORS
        - Attempt count < MAX_RETRIES
        """
        if attempt >= self.MAX_RETRIES:
            return False
        
        if result.executed:
            return False  # Success, no retry needed
        
        if result.error_code in self.RETRIABLE_ERRORS:
            logger.info(
                f"Retry eligible: error={result.error_code}, attempt={attempt}/{self.MAX_RETRIES}"
            )
            return True
        
        logger.info(
            f"Retry NOT eligible: error={result.error_code} (not retriable)"
        )
        return False
    
    def _journal_retry(self, plan: OrderPlan, attempt: int, reason: str):
        """Journal retry attempt"""
        if self.journal_callback:
            self.journal_callback(
                event_type="RETRY_ATTEMPT",
                plan_id=plan.id,
                detail=f"Retry attempt {attempt}/{self.MAX_RETRIES}: {reason}",
                metadata={
                    "verdict_id": plan.verdict_id,
                    "retry_attempt": attempt,
                    "max_retries": self.MAX_RETRIES
                }
            )
    
    def execute_with_retry(
        self,
        adapter,
        plan: OrderPlan
    ) -> ExecutionResult:
        """
        Execute order with automatic retry on network errors.
        
        Args:
            adapter: Exchange adapter
            plan: Order plan
            
        Returns:
            ExecutionResult (from final attempt)
        """
        result = None
        
        for attempt in range(self.MAX_RETRIES + 1):  # 0, 1, 2 (3 total attempts)
            # Attempt execution
            logger.info(
                f"Execution attempt {attempt + 1}/{self.MAX_RETRIES + 1}: "
                f"{plan.symbol} {plan.side} {plan.quantity}"
            )
            
            result = adapter.place_order(plan)
            
            # Success → return immediately
            if result.executed:
                if attempt > 0:
                    logger.info(f"✅ Retry succeeded on attempt {attempt + 1}")
                return result
            
            # Check if retry allowed
            if not self._should_retry(result, attempt):
                logger.info(
                    f"❌ No retry: error={result.error_code}, attempt={attempt}"
                )
                return result
            
            # Journal retry attempt
            self._journal_retry(
                plan,
                attempt + 1,
                f"Network error: {result.error_detail}"
            )
            
            # Backoff before retry
            if attempt < len(self.BACKOFF_SCHEDULE):
                backoff_seconds = self.BACKOFF_SCHEDULE[attempt]
                logger.info(f"⏳ Backing off {backoff_seconds}s before retry...")
                time.sleep(backoff_seconds)
        
        # All retries exhausted
        logger.error(
            f"🔴 All retries exhausted: {plan.symbol} {plan.side}, "
            f"final error={result.error_code}"
        )
        return result
