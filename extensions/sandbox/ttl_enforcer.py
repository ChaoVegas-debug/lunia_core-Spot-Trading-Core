"""
PHASE 9.3 — TTL ENFORCER

Pure time-to-live logic for position expiry.

No state, just deterministic time checks.
"""

from typing import Optional


def is_ttl_expired(
    open_ts_ms: int,
    now_ts_ms: int,
    time_limit_ms: Optional[int],
) -> bool:
    """
    Check if position has exceeded time-to-live limit.
    
    Args:
        open_ts_ms: Position open timestamp (milliseconds)
        now_ts_ms: Current timestamp (milliseconds)
        time_limit_ms: Time limit in milliseconds (None = never expires)
        
    Returns:
        True if position is expired, False otherwise
    """
    if time_limit_ms is None:
        return False  # No TTL set
    
    if time_limit_ms <= 0:
        return False  # Invalid TTL, treat as no limit
    
    elapsed_ms = now_ts_ms - open_ts_ms
    return elapsed_ms >= time_limit_ms
