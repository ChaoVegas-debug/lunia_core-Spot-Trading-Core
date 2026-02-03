"""
EPOCH C: Execution Exceptions
Hard vs Soft error classification for ambiguous-state handling
"""
from __future__ import annotations


class ExecutionError(Exception):
    """Base execution error"""
    pass


class HardError(ExecutionError):
    """
    Definitive rejection - safe to mark FAILED
    
    Examples:
    - Invalid symbol
    - Insufficient funds
    - Auth failure
    - Exchange explicit reject (4xx validation/business)
    """
    pass


class SoftError(ExecutionError):
    """
    Ambiguous outcome - MUST NOT mark FAILED
    
    Examples:
    - Network timeout
    - Connection reset
    - 502/503/504 errors
    - Adapter exception after request sent
    
    Keep status SUBMITTING and reconcile later.
    """
    pass


class NetworkError(SoftError):
    """Network/transport errors"""
    pass


class TimeoutError(SoftError):
    """Request timeout errors"""
    pass


class UpstreamError(SoftError):
    """Upstream service errors (502/503/504)"""
    pass
