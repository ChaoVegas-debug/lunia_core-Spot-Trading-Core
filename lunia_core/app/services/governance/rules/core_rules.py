"""
EPOCH E Phase E2: Core Governance Rules
Minimal institutional rule set for capital safety
"""
from __future__ import annotations

import math
import os
import time

from .base import GovernanceRule, RuleResult
from lunia_core.app.services.strategy.models import IntentProposal
from lunia_core.app.services.market_data.realtime.models import MarketSnapshot, SnapshotState
from lunia_core.app.services.governance.context import GovernanceContext


class MarketValidityRule(GovernanceRule):
    """
    Validate market data is fresh and valid
    
    Checks:
    - snapshot.snapshot_state == VALID
    - snapshot age < staleness_threshold_ms
    
    Reason codes:
    - GOV_MD_INVALID (snapshot not VALID)
    - GOV_MD_STALE (snapshot too old)
    """
    
    def __init__(self, staleness_threshold_ms: int | None = None):
        """
        Initialize market validity rule
        
        Args:
            staleness_threshold_ms: Max snapshot age (default from env, fallback 5000ms)
        """
        if staleness_threshold_ms is None:
            staleness_threshold_ms = int(os.getenv("LUNIA_GOV_STALENESS_MS", "5000"))
        
        self._staleness_threshold_ms = staleness_threshold_ms
    
    @property
    def rule_id(self) -> str:
        return "market_validity_v1"
    
    def evaluate(
        self,
        intent: IntentProposal,
        snapshot: MarketSnapshot,
        context: GovernanceContext
    ) -> RuleResult:
        """Evaluate market validity"""
        # Check snapshot state (handle both enum and string due to use_enum_values)
        snapshot_state = snapshot.snapshot_state
        if isinstance(snapshot_state, str):
            is_valid = snapshot_state == "VALID"
        else:
            is_valid = snapshot_state == SnapshotState.VALID
        
        if not is_valid:
            return RuleResult(
                passed=False,
                reason_code="GOV_MD_INVALID",
                metadata={
                    "snapshot_state": str(snapshot_state),
                    "symbol": intent.symbol
                }
            )
        
        # Check snapshot age
        now_ms = int(time.time() * 1000)
        age_ms = now_ms - snapshot.last_update_ms
        
        if age_ms > self._staleness_threshold_ms:
            return RuleResult(
                passed=False,
                reason_code="GOV_MD_STALE",
                metadata={
                    "age_ms": age_ms,
                    "threshold_ms": self._staleness_threshold_ms,
                    "symbol": intent.symbol
                }
            )
        
        # Passed
        return RuleResult(
            passed=True,
            reason_code="OK",
            metadata={}
        )


class PriceSanityEchoRule(GovernanceRule):
    """
    Double-check price sanity (defense in depth)
    
    Checks:
    - intent.reference_price vs snapshot.mid_price
    - deviation < band_pct
    
    Reason code:
    - GOV_PRICE_DEVIATION
    
    Note: This duplicates execution guards by design.
    Governance sees the price BEFORE execution,
    giving a second chance to block bad prices.
    """
    
    def __init__(self, band_pct: float | None = None):
        """
        Initialize price sanity echo rule
        
        Args:
            band_pct: Max price deviation (default from env, fallback 5.0%)
        """
        if band_pct is None:
            try:
                band_pct = float(os.getenv("LUNIA_GOV_PRICE_BAND_PCT", "5.0"))
            except (ValueError, TypeError):
                band_pct = 5.0
        
        # Validate band_pct
        if not (0 < band_pct <= 50):
            band_pct = 5.0  # Fail-safe default
        
        self._band_pct = band_pct
    
    @property
    def rule_id(self) -> str:
        return "price_sanity_echo_v1"
    
    def evaluate(
        self,
        intent: IntentProposal,
        snapshot: MarketSnapshot,
        context: GovernanceContext
    ) -> RuleResult:
        """Evaluate price sanity"""
        # Skip if no reference price
        if intent.reference_price is None:
            return RuleResult(
                passed=True,
                reason_code="OK",
                metadata={"reason": "no_reference_price"}
            )
        
        # Get current mid price
        current_mid = snapshot.mid_price
        
        if current_mid is None or not math.isfinite(current_mid) or current_mid <= 0:
            return RuleResult(
                passed=False,
                reason_code="GOV_PRICE_DEVIATION",
                metadata={
                    "reason": "invalid_mid_price",
                    "mid_price": current_mid
                }
            )
        
        # Compute deviation
        deviation_pct = abs(intent.reference_price - current_mid) / current_mid * 100.0
        
        # Check band
        if deviation_pct > self._band_pct:
            return RuleResult(
                passed=False,
                reason_code="GOV_PRICE_DEVIATION",
                metadata={
                    "reference_price": intent.reference_price,
                    "current_mid_price": current_mid,
                    "deviation_pct": round(deviation_pct, 2),
                    "band_pct": self._band_pct,
                    "symbol": intent.symbol
                }
            )
        
        # Passed
        return RuleResult(
            passed=True,
            reason_code="OK",
            metadata={"deviation_pct": round(deviation_pct, 2)}
        )


class StrategyCooldownRule(GovernanceRule):
    """
    Enforce strategy execution cooldown (stateful)
    
    Checks:
    - context.last_execution_times[strategy_id][symbol]
    - If too recent (< cooldown_ms) → REJECT
    
    Reason code:
    - GOV_STRATEGY_COOLDOWN
    
    This prevents strategies from spamming intents.
    """
    
    def __init__(self, cooldown_ms: int | None = None):
        """
        Initialize strategy cooldown rule
        
        Args:
            cooldown_ms: Min time between executions (default from env, fallback 60000ms = 1min)
        """
        if cooldown_ms is None:
            cooldown_ms = int(os.getenv("LUNIA_GOV_COOLDOWN_MS", "60000"))
        
        self._cooldown_ms = cooldown_ms
    
    @property
    def rule_id(self) -> str:
        return "strategy_cooldown_v1"
    
    def evaluate(
        self,
        intent: IntentProposal,
        snapshot: MarketSnapshot,
        context: GovernanceContext
    ) -> RuleResult:
        """Evaluate strategy cooldown (stateful)"""
        # Get last execution time
        last_exec_ms = context.get_last_execution_time(intent.strategy_id, intent.symbol)
        
        if last_exec_ms == 0:
            # Never executed before → allow
            return RuleResult(
                passed=True,
                reason_code="OK",
                metadata={"first_execution": True}
            )
        
        # Check time since last execution
        now_ms = int(time.time() * 1000)
        time_since_last_ms = now_ms - last_exec_ms
        
        if time_since_last_ms < self._cooldown_ms:
            return RuleResult(
                passed=False,
                reason_code="GOV_STRATEGY_COOLDOWN",
                metadata={
                    "strategy_id": intent.strategy_id,
                    "symbol": intent.symbol,
                    "time_since_last_ms": time_since_last_ms,
                    "cooldown_ms": self._cooldown_ms,
                    "remaining_ms": self._cooldown_ms - time_since_last_ms
                }
            )
        
        # Passed
        return RuleResult(
            passed=True,
            reason_code="OK",
            metadata={"time_since_last_ms": time_since_last_ms}
        )
