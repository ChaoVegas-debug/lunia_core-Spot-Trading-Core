"""
Epoch C.1: Rate Limit Guard

Token bucket rate limiter per exchange adapter.

ENFORCEMENT RULE:
- If rate exceeded → Block execution with error_code="RATE_LIMIT"
- FAIL-CLOSED: Prefer blocking over violating exchange limits
"""
import time
import logging
from typing import Dict
from threading import Lock

logger = logging.getLogger(__name__)


class TokenBucket:
    """
    Token bucket algorithm for rate limiting.
    
    Tokens refill at constant rate. Each order consumes 1 token.
    """
    
    def __init__(self, capacity: float, refill_rate: float):
        """
        Args:
            capacity: Max tokens (burst capacity)
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill_time = time.time()
        self.lock = Lock()
    
    def consume(self, tokens: float = 1.0) -> bool:
        """
        Try to consume tokens.
        
        Returns:
            True if tokens available, False if rate limited
        """
        with self.lock:
            now = time.time()
            elapsed = now - self.last_refill_time
            
            # Refill tokens based on elapsed time
            self.tokens = min(
                self.capacity,
                self.tokens + (elapsed * self.refill_rate)
            )
            self.last_refill_time = now
            
            # Try to consume
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            else:
                return False


class RateLimitGuard:
    """
    Per-exchange rate limit enforcer.
    
    Uses token bucket algorithm to prevent exchange API bans.
    """
    
    def __init__(self, max_orders_per_second: float = 5.0):
        """
        Args:
            max_orders_per_second: Max order rate (default 5/sec per exchange)
        """
        self.max_rate = max_orders_per_second
        self.buckets: Dict[str, TokenBucket] = {}
        self.buckets_lock = Lock()
        
        logger.info(f"RateLimitGuard initialized: {max_orders_per_second}/sec per exchange")
    
    def _get_bucket(self, adapter_name: str) -> TokenBucket:
        """Get or create token bucket for adapter"""
        with self.buckets_lock:
            if adapter_name not in self.buckets:
                self.buckets[adapter_name] = TokenBucket(
                    capacity=self.max_rate,  # Burst capacity = 1 second worth
                    refill_rate=self.max_rate  # Refill at max rate
                )
                logger.debug(f"Created token bucket for {adapter_name}")
            
            return self.buckets[adapter_name]
    
    def check(self, adapter_name: str) -> bool:
        """
        Check if order is allowed under rate limit.
        
        Args:
            adapter_name: Exchange adapter name
            
        Returns:
            True if allowed, False if rate limited
        """
        bucket = self._get_bucket(adapter_name)
        allowed = bucket.consume(1.0)
        
        if not allowed:
            logger.warning(
                f"🚫 RATE LIMIT: {adapter_name} exceeded {self.max_rate}/sec"
            )
        
        return allowed
    
    def reset(self, adapter_name: str) -> None:
        """Reset bucket for adapter (for testing)"""
        with self.buckets_lock:
            if adapter_name in self.buckets:
                del self.buckets[adapter_name]
