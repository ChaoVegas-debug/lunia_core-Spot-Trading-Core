"""Override Policy (PHASE 2)

Typed override mechanism with strict token validation.
Invalid token = CRASH (architectural violation).
"""
from dataclasses import dataclass
from typing import Optional


# CANONICAL OVERRIDE TOKEN (do NOT modify)
OVERRIDE_TOKEN = "I_UNDERSTAND_ENFORCEMENT_OVERRIDE_PHASE2"


@dataclass
class RiskOverride:
    """Typed override for enforcement bypass (audit trail).
    
    PHASE 2:
    - token: must match OVERRIDE_TOKEN exactly
    - actor: who requested override (for audit)
    - reason: why override was needed (for audit)
    - timestamp: when override was issued
    """
    
    token: str
    actor: str
    reason: str
    timestamp: float


class ArchitecturalViolationError(Exception):
    """Raised when override token is invalid.
    
    This is an architectural failure, not a normal error.
    System must crash loudly - no silent bypass.
    """
    pass


def validate_override(override: Optional[RiskOverride]) -> bool:
    """Validate override token.
    
    Args:
        override: RiskOverride instance or None
        
    Returns:
        True if valid, False if absent
        
    Raises:
        ArchitecturalViolationError: If token present but invalid
    """
    if override is None:
        return False
    
    if override.token == OVERRIDE_TOKEN:
        return True
    
    # Invalid token = architectural failure
    raise ArchitecturalViolationError(
        f"[PHASE2_FAIL] Invalid override token. "
        f"Expected: '{OVERRIDE_TOKEN}', "
        f"Got: '{override.token}'. "
        f"This is an architectural violation - override must use exact token or be absent."
    )
