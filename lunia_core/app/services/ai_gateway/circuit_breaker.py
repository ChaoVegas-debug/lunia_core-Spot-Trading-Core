"""
AI Gateway: Circuit Breaker

Fail-fast circuit breaker to prevent cascading AI failures.

States:
- CLOSED: Normal operation
- OPEN: Failures exceeded threshold, reject all requests
- HALF_OPEN: Testing recovery after timeout
"""
import time
from enum import Enum
from threading import Lock
from typing import Optional


class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """
    Circuit breaker for AI Gateway.
    
    After failure_threshold consecutive failures, circuit opens for timeout_seconds.
    During OPEN state, all requests are rejected immediately (fail-fast).
    """
    
    def __init__(self, failure_threshold: int = 5, timeout_seconds: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.lock = Lock()
    
    def can_execute(self) -> bool:
        """Check if request can be executed."""
        with self.lock:
            if self.state == CircuitState.CLOSED:
                return True
            
            if self.state == CircuitState.OPEN:
                # Check if timeout has elapsed
                if self.last_failure_time and (time.time() - self.last_failure_time) > self.timeout_seconds:
                    # Try recovery (HALF_OPEN state)
                    self.state = CircuitState.HALF_OPEN
                    return True
                return False  # Still OPEN, reject
            
            if self.state == CircuitState.HALF_OPEN:
                return True  # Allow one test request
            
            return False
    
    def record_success(self):
        """Record successful execution."""
        with self.lock:
            self.success_count += 1
            self.failure_count = 0  # Reset failure counter
            
            if self.state == CircuitState.HALF_OPEN:
                # Recovery successful, close circuit
                self.state = CircuitState.CLOSED
    
    def record_failure(self):
        """Record failed execution."""
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                # Recovery failed, re-open circuit
                self.state = CircuitState.OPEN
            
            if self.failure_count >= self.failure_threshold:
                # Threshold exceeded, open circuit
                self.state = CircuitState.OPEN
    
    def get_stats(self) -> dict:
        """Get circuit breaker statistics."""
        with self.lock:
            return {
                "state": self.state.value,
                "failure_count": self.failure_count,
                "success_count": self.success_count,
                "last_failure_time": self.last_failure_time
            }
