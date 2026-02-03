"""Emergency Intent Contract (PHASE 3)

Defines TradeIntent with emergency escape hatch.
Emergency is REDUCE-ONLY (SELL), never BUY.
"""
from dataclasses import dataclass
from typing import Optional
from forensic.risk.policy import ArchitecturalViolationError


@dataclass
class TradeIntent:
    """Trade intent with optional emergency bypass.
    
    PHASE 3 ADDITION:
    - is_emergency: Explicit emergency flag (manual trigger only)
    - emergency_reason: Audit trail for why emergency was declared
    
    CONSTITUTIONAL RULE:
    Emergency BUY is FORBIDDEN (architectural violation).
    """
    
    id: str
    side: str  # "BUY" | "SELL"
    order_type: str  # "MARKET" | "LIMIT"
    qty: 'Decimal'
    
    # PHASE 3: Emergency escape hatch
    is_emergency: bool = False
    emergency_reason: Optional[str] = None
    
    # Optional metadata
    metadata: Optional[dict] = None
    
    def __post_init__(self):
        """Enforce emergency constitution."""
        if self.is_emergency and self.side == "BUY":
            raise ArchitecturalViolationError(
                "[PHASE3_VIOLATION] EMERGENCY_BUY_FORBIDDEN: "
                "Safety Valve is reduce-only. Emergency intents may only SELL. "
                f"intent_id={self.id}, side={self.side}, "
                f"emergency_reason={self.emergency_reason}"
            )
        
        # Validate side
        if self.side not in ["BUY", "SELL"]:
            raise ValueError(f"Invalid side: {self.side}. Must be BUY or SELL.")
