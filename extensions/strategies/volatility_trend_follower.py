"""
PHASE 9.4 — VOLATILITY TREND FOLLOWER

Archetype: Trend-following via volatility + ATR proxy (snapshot-only).

COST AWARENESS: Expected move must exceed 2x estimated costs (K=2).
GOVERNANCE FIRST: Respects all governance blocks.
DETERMINISTIC: No randomness, no history dependency.
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


class VolatilityTrendFollower:
    """
    Volatility-aware trend follower with deterministic cost gate.
    
    GATES:
    1. Governance (reduce_only, allow_new_entries, risk_state)
    2. Volatility (NORMAL or ELEVATED only)
    3. Data availability (atr_14 > 0)
    4. Cost (expected_move >= 2.0 * estimated_cost)
    """
    
    STRATEGY_ID = "volatility_trend_follower_v1"
    
    # Cost model constants (deterministic)
    FEE_BPS = 4.0  # 0.04% = 4 bp conservative estimate
    SLIP_BPS_NORMAL = 2.0  # NORMAL volatility: 2 bp
    SLIP_BPS_ELEVATED = 5.0  # ELEVATED volatility: 5 bp
    
    # Entry sizing (conservative)
    SIZE_FRACTION = 0.02  # 2% of equity
    
    # Exit plan parameters
    STOP_LOSS_PCT = 2.0
    TAKE_PROFIT_PCT = 6.0
    TTL_MS = 4 * 60 * 60 * 1000  # 4 hours
    
    @classmethod
    def generate_intent(
        cls,
        governance: GovernanceContext,
        portfolio: ShadowPortfolio,
        markets: List[MarketSnapshot],
    ) -> StrategyIntent:
        """
        Generate intent with cost-aware gating.
        
        Returns NOOP if any gate fails, ENTRY if all pass.
        """
        if not markets:
            return cls._create_noop(governance, "No markets available")
        
        market = markets[0]
        
        # Gate 1: Governance blocks
        governance_block = cls._check_governance_blocks(governance)
        if governance_block:
            return cls._create_noop(governance, governance_block)
        
        # Gate 2: Volatility filter (NORMAL or ELEVATED only)
        if market.volatility_state not in [VolatilityState.NORMAL, VolatilityState.ELEVATED]:
            return cls._create_noop(
                governance,
                f"Volatility gate: state={market.volatility_state.value} (need NORMAL or ELEVATED)"
            )
        
        # Gate 3: Data availability
        if market.atr_14 <= 0:
            return cls._create_noop(governance, "Insufficient market data: atr_14 missing/zero")
        
        # Calculate expected move (ATR proxy or minimum 0.2%)
        expected_move = max(market.atr_14 * 0.5, market.mid * 0.002)
        
        # Calculate estimated cost
        estimated_cost = cls._estimate_cost(market)
        
        # Gate 4: Cost gate (K=2)
        if expected_move < 2.0 * estimated_cost:
            return cls._create_noop(
                governance,
                f"Cost Gate: expected_move={expected_move:.8f} < 2.0*estimated_cost={2.0*estimated_cost:.8f}"
            )
        
        # All gates passed -> ENTRY
        return cls._create_entry(governance, market, portfolio, expected_move, estimated_cost)
    
    @classmethod
    def _check_governance_blocks(cls, governance: GovernanceContext) -> str:
        """Check for governance blocks. Returns reason if blocked, empty string otherwise."""
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
        """Estimate total execution cost in price terms (deterministic)."""
        # Spread cost
        estimated_spread = market.mid * market.spread_pct
        
        # Slippage cost (volatility-dependent)
        if market.volatility_state == VolatilityState.NORMAL:
            slip_bps = cls.SLIP_BPS_NORMAL
        else:  # ELEVATED
            slip_bps = cls.SLIP_BPS_ELEVATED
        estimated_slip = market.mid * (slip_bps / 10000.0)
        
        # Fee cost
        estimated_fee = market.mid * (cls.FEE_BPS / 10000.0)
        
        return estimated_spread + estimated_slip + estimated_fee
    
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
        
        # Calculate size (conservative: 2% of equity)
        size_base = (portfolio.equity * cls.SIZE_FRACTION) / market.mid
        
        # Exit plan with SL + TP + TTL
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
            f"Volatility Trend: vol_state={market.volatility_state.value} | "
            f"spread_pct={market.spread_pct:.6f} | "
            f"expected_move={expected_move:.8f} | "
            f"estimated_cost={estimated_cost:.8f} | "
            f"ratio={expected_move/estimated_cost:.2f}x | "
            f"Cost Gate PASS (K=2)"
        )
        
        return StrategyIntent(
            intent_id=intent_id,
            ts_ms=governance.ts_ms,
            protocol_version=PROTOCOL_VERSION,
            correlation_id=governance.correlation_id,
            intent_type=IntentType.ENTRY,
            direction=TradeDirection.LONG,  # Reference: long-only for v1
            symbol=market.symbol,
            size_base=size_base,
            size_quote=None,
            exit_plan=exit_plan,
            confidence=0.7,
            rationale=rationale,
            strategy_id=cls.STRATEGY_ID,
            strategy_frequency=StrategyFrequency.INTRADAY,
        )
    
    @classmethod
    def _create_noop(cls, governance: GovernanceContext, reason: str) -> StrategyIntent:
        """Create NOOP intent with rationale."""
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
            strategy_frequency=StrategyFrequency.INTRADAY,
        )
    
    @staticmethod
    def _generate_intent_id(correlation_id: str, ts_ms: int, intent_type: str) -> str:
        """Generate deterministic intent ID."""
        payload = f"{correlation_id}:{ts_ms}:volatility_trend_follower_v1:{intent_type}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
