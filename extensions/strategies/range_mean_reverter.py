"""
PHASE 9.4 — RANGE MEAN REVERTER

Archetype: Mean reversion in low/normal volatility with strict cost gate.

COST AWARENESS: Expected move must exceed 3x estimated costs (K=3).
KNIFE-CATCH PREVENTION: Forbids HIGH/EXTREME volatility.
DETERMINISTIC: Snapshot-only signal.
"""

import hashlib
from typing import List

from extensions.protocol.protocol import (
    PROTOCOL_VERSION,
    GovernanceContext,
    MarketSnapshot,
    ShadowPortfolio,
    StrategyIntent,
    TradeExitPlan,
    IntentType,
    TradeDirection,
    StrategyFrequency,
    VolatilityState,
    RiskState,
)


class RangeMeanReverter:
    """
    Mean reversion strategy with strict cost and volatility gates.
    
    GATES:
    1. Governance (standard blocks)
    2. Volatility (CALM or NORMAL only - no knife catching)
    3. Data availability (spread_pct, atr_14)
    4. Cost (expected_move >= 3.0 * estimated_cost)
    """
    
    STRATEGY_ID = "range_mean_reverter_v1"
    
    # Cost model constants
    FEE_BPS = 4.0  # Conservative fee estimate
    SPREAD_MULTIPLIER = 2.0  # Spread cost amplified for round-trip
    ADDITIONAL_COST_BPS = 8.0  # Additional friction buffer
    
    # Entry sizing
    SIZE_FRACTION = 0.015  # 1.5% of equity (smaller than trend)
    
    # Exit plan parameters (tight for mean reversion)
    STOP_LOSS_PCT = 1.5
    TAKE_PROFIT_PCT = 3.5
    TTL_MS =60 * 60 * 1000  # 1 hour
    
    @classmethod
    def generate_intent(
        cls,
        governance: GovernanceContext,
        portfolio: ShadowPortfolio,
        markets: List[MarketSnapshot],
    ) -> StrategyIntent:
        """
        Generate mean reversion intent with strict gating.
        
        Returns NOOP if any gate fails, ENTRY if all pass.
        """
        if not markets:
            return cls._create_noop(governance, "No markets available")
        
        market = markets[0]
        
        # Gate 1: Governance blocks
        governance_block = cls._check_governance_blocks(governance)
        if governance_block:
            return cls._create_noop(governance, governance_block)
        
        # Gate 2: Volatility filter (CALM or NORMAL only - knife-catch prevention)
        if market.volatility_state not in [VolatilityState.CALM, VolatilityState.NORMAL]:
            return cls._create_noop(
                governance,
                f"Volatility Too High: state={market.volatility_state.value} (need CALM or NORMAL)"
            )
        
        # Gate 3: Data availability
        if market.spread_pct <= 0:
            return cls._create_noop(governance, "Insufficient market data: spread_pct missing/zero")
        
        # Calculate deviation proxy (snapshot-only)
        deviation_proxy = max(market.mid * (market.spread_pct * 3.0), market.atr_14 * 0.3)
        
        if deviation_proxy <= 0:
            return cls._create_noop(governance, "Insufficient signal: deviation_proxy <= 0")
        
        # Expected move = deviation proxy
        expected_move = deviation_proxy
        
        # Calculate estimated cost
        estimated_cost = cls._estimate_cost(market)
        
        # Gate 4: Strict cost gate (K=3)
        if expected_move < 3.0 * estimated_cost:
            return cls._create_noop(
                governance,
                f"Cost Gate: expected_move={expected_move:.8f} < 3.0*estimated_cost={3.0*estimated_cost:.8f}"
            )
        
        # All gates passed -> ENTRY
        return cls._create_entry(governance, market, portfolio, expected_move, estimated_cost)
    
    @classmethod
    def _check_governance_blocks(cls, governance: GovernanceContext) -> str:
        """Check for governance blocks."""
        if governance.emergency_override_active:
            return "Governance: emergency_override_active"
        if governance.is_reduce_only:
            return "Governance: reduce_only_mode"
        if not governance.allow_new_entries:
            return "Governance: new_entries_blocked"
        if governance.risk_state in [RiskState.RED, RiskState.BLACK]:
            return f"Governance: risk_state={governance.risk_state.value}"
        return ""
    
    @classmethod
    def _estimate_cost(cls, market: MarketSnapshot) -> float:
        """Estimate total execution cost (deterministic, conservative)."""
        # Spread cost (amplified for round-trip)
        estimated_spread = market.mid * market.spread_pct * cls.SPREAD_MULTIPLIER
        
        # Additional cost buffer
        additional_cost = market.mid * (cls.ADDITIONAL_COST_BPS / 10000.0)
        
        return estimated_spread + additional_cost
    
    @classmethod
    def _create_entry(
        cls,
        governance: GovernanceContext,
        market: MarketSnapshot,
        portfolio: ShadowPortfolio,
        expected_move: float,
        estimated_cost: float,
    ) -> StrategyIntent:
        """Create ENTRY intent."""
        intent_id = cls._generate_intent_id(governance.correlation_id, governance.ts_ms, "entry")
        
        # Calculate size (1.5% of equity)
        size_base = (portfolio.equity * cls.SIZE_FRACTION) / market.mid
        
        # Exit plan with tight SL/TP + TTL
        exit_plan = TradeExitPlan(
            stop_loss_price=None,
            stop_loss_pct=cls.STOP_LOSS_PCT,
            take_profit_price=None,
            take_profit_pct=cls.TAKE_PROFIT_PCT,
            time_limit_ms=cls.TTL_MS,
            trail_start_pct=None,
        )
        
        # Rationale with numeric evidence
        rationale = (
            f"Range Mean Reversion: vol_state={market.volatility_state.value} | "
            f"spread_pct={market.spread_pct:.6f} | "
            f"expected_move={expected_move:.8f} | "
            f"estimated_cost={estimated_cost:.8f} | "
            f"ratio={expected_move/estimated_cost:.2f}x | "
            f"Cost Gate PASS (K=3)"
        )
        
        return StrategyIntent(
            intent_id=intent_id,
            ts_ms=governance.ts_ms,
            protocol_version=PROTOCOL_VERSION,
            correlation_id=governance.correlation_id,
            intent_type=IntentType.ENTRY,
            direction=TradeDirection.LONG,  # Reference: long-only
            symbol=market.symbol,
            size_base=size_base,
            size_quote=None,
            exit_plan=exit_plan,
            confidence=0.65,
            rationale=rationale,
            strategy_id=cls.STRATEGY_ID,
            strategy_frequency=StrategyFrequency.SWING,
        )
    
    @classmethod
    def _create_noop(cls, governance: GovernanceContext, reason: str) -> StrategyIntent:
        """Create NOOP intent."""
        intent_id = cls._generate_intent_id(governance.correlation_id, governance.ts_ms, "noop")
        
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
            confidence=1.0,
            rationale=f"{cls.STRATEGY_ID}: {reason}",
            strategy_id=cls.STRATEGY_ID,
            strategy_frequency=StrategyFrequency.SWING,
        )
    
    @staticmethod
    def _generate_intent_id(correlation_id: str, ts_ms: int, intent_type: str) -> str:
        """Generate deterministic intent ID."""
        payload = f"{correlation_id}:{ts_ms}:range_mean_reverter_v1:{intent_type}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
