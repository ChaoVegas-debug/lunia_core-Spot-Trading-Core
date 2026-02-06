"""
Epoch 10: Council Registry

Deterministic ordering/loading of council members.
"""
from typing import List

from .members import (
    CouncilMember,
    MarketSafetyMember,
    LiquiditySafetyMember,
    MetricsGuardMember,
    AIShadowAdvisorMember
)


def get_council_members() -> List[CouncilMember]:
    """
    Get all mandatory council members in deterministic order.
    
    Order matters for audit trail consistency.
    """
    return [
        MarketSafetyMember(),
        LiquiditySafetyMember(),
        MetricsGuardMember(min_acceptance_rate=0.5),
        AIShadowAdvisorMember()
    ]
