"""
Lifecycle Service — Capital Allocation & Position Lifecycle Management

Epoch C.3: The Autopilot Layer

Responsibilities:
- Deterministic capital sizing (confidence + volatility scaling)
- Mandatory exit plan creation at entry
- Autonomous exit monitoring and order generation
- Integration with Council and Risk Governor
"""

from lunia_core.app.services.lifecycle.models import (
    AllocationPolicy,
    ExitPlan,
    VolatilityRegime,
)

__all__ = [
    "AllocationPolicy",
    "ExitPlan",
    "VolatilityRegime",
]
