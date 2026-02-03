"""Risk Configuration (PHASE 2)

Config-driven risk modes: SHADOW (default) vs ENFORCE.
No global flags - config injected into gate.
"""
from enum import Enum
from dataclasses import dataclass
from decimal import Decimal


class RiskMode(Enum):
    """Risk gate operating mode."""
    SHADOW = "SHADOW"    # Observe only, never block (Phase 1 behavior)
    ENFORCE = "ENFORCE"  # Block execut when limits breached (Phase 2)


@dataclass
class RiskConfig:
    """Risk configuration (immutable per run).
    
    PHASE 2:
    - mode: SHADOW (default, backward compatible) or ENFORCE
    - max_drawdown: threshold for blocking (25% canonical)
    - override_enabled: allow override mechanism
    - fail_closed: treat errors as blocks
    """
    
    mode: RiskMode = RiskMode.SHADOW  # DEFAULT: backward compatible with Phase 1
    max_drawdown: Decimal = Decimal("0.25")  # 25% canonical limit
    override_enabled: bool = True
    fail_closed: bool = True
    decision_id_salt: str = "PHASE2_AUDIT"
    
    def __post_init__(self):
        """Validate Decimal types."""
        if not isinstance(self.max_drawdown, Decimal):
            raise TypeError(f"max_drawdown must be Decimal, got {type(self.max_drawdown)}")
