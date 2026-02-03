"""
PHASE 9.1 — REFERENCE NOOP STRATEGY

Reference implementation validating:
- Protocol compliance
- Governance flow
- Determinism
- Traceability

INVARIANT: Never intended to trade real capital.

This strategy deliberately does nothing except document the decision
to do nothing, creating a full audit trail for governance verification.
"""

import hashlib
import time
from typing import List

from extensions.protocol.protocol import (
    PROTOCOL_VERSION,
    GovernanceContext,
    MarketSnapshot,
    ShadowPortfolio,
    StrategyIntent,
    StrategyManifest,
    IntentType,
    StrategyFrequency,
)


class ReferenceNoopStrategy:
    """
    Reference NOOP strategy for protocol validation.
    
    GUARANTEES:
    - Always returns NOOP intent
    - Full governance compliance
    - Deterministic correlation tracking
    - Complete audit traceability
    """

    MANIFEST = StrategyManifest(
        strategy_id="reference_noop_v1",
        name="Reference NOOP Strategy",
        version="1.0.0",
        protocol_version=PROTOCOL_VERSION,
        author="LUNIA Core Team",
        frequency=StrategyFrequency.POSITION,
        supports_long=False,
        supports_short=False,
        requires_hedging=False,
        max_leverage=1.0,
        preferred_timeframe="1d",
    )

    @classmethod
    def generate_intent(
        cls,
        governance: GovernanceContext,
        portfolio: ShadowPortfolio,
        markets: List[MarketSnapshot],
    ) -> StrategyIntent:
        """
        Generate NOOP intent with full traceability.
        
        Args:
            governance: Current governance context
            portfolio: Current portfolio snapshot
            markets: Available market snapshots
            
        Returns:
            NOOP intent with deterministic ID and audit trail
        """
        # Generate deterministic intent ID from context
        intent_id = cls._generate_intent_id(
            governance.correlation_id,
            governance.ts_ms,
        )

        # Build governance-aware rationale
        rationale_parts = [
            "Reference NOOP strategy",
            f"run_id={governance.run_id}",
            f"risk_state={governance.risk_state.value}",
        ]

        if governance.emergency_override_active:
            rationale_parts.append("emergency_override_active=true")

        if governance.is_reduce_only:
            rationale_parts.append("reduce_only_mode=true")

        rationale = " | ".join(rationale_parts)

        # Create NOOP intent
        return StrategyIntent(
            intent_id=intent_id,
            ts_ms=governance.ts_ms,
            protocol_version=PROTOCOL_VERSION,
            correlation_id=governance.correlation_id,
            intent_type=IntentType.NOOP,
            direction=None,
            symbol=None,
            size_base=None,
            size_quote=None,
            exit_plan=None,
            confidence=1.0,  # 100% confident in doing nothing
            rationale=rationale,
            strategy_id=cls.MANIFEST.strategy_id,
            strategy_frequency=cls.MANIFEST.frequency,
            is_hedge=False,
            is_scaling=False,
        )

    @staticmethod
    def _generate_intent_id(correlation_id: str, ts_ms: int) -> str:
        """
        Generate deterministic intent ID.
        
        GUARANTEE: Same inputs always produce same ID (replay-safe).
        
        Args:
            correlation_id: Governance correlation ID
            ts_ms: Timestamp in milliseconds
            
        Returns:
            Deterministic SHA256-based intent ID
        """
        payload = f"{correlation_id}:{ts_ms}:reference_noop_v1"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def validate_manifest(cls) -> bool:
        """
        Validate manifest protocol compatibility.
        
        Returns:
            True if manifest is valid
        """
        return cls.MANIFEST.is_valid


# ────────────────────────────────────────────────────────────────────────────────
# MODULE-LEVEL VALIDATION
# ────────────────────────────────────────────────────────────────────────────────

assert ReferenceNoopStrategy.validate_manifest(), (
    f"Protocol version mismatch: "
    f"strategy={ReferenceNoopStrategy.MANIFEST.protocol_version} "
    f"!= core={PROTOCOL_VERSION}"
)
