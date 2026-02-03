"""
PHASE 9.4 — BREAKOUT SCALP

Archetype: Liquidity-aware scalp in high volatility with aggressive cost gate.

COST AWARENESS: Expected move must exceed 1.5x estimated costs (K=1.5).
LIQUIDITY GATE: Strict spread_pct threshold.
HIGH VOLATILITY ONLY: Trades breakouts in ELEVATED volatility.
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


class BreakoutScalp:
    """
    High-volatility scalp with strict liquidity and cost gates.
    
    GATES:
    1. Governance (standard blocks)
    2. Volatility (ELEVATED only)
    3. Liquidity (spread_pct <= threshold)
    4. Cost (expected_move >= 1.5 * estimated_cost)
    """
    
    STRATEGY_ID = "breakout_scalp_v1"
    
    # Liquidity gate
    MAX_SPREAD_PCT = 0.0015  # 0.15% max spread
    
    # Cost model constants
    FEE_BPS = 4.0
    SLIP_BPS = 6.0  # Higher for scalp
    
    # Entry sizing (very small for scalp)
    SIZE_FRACTION = 0.01  # 1% of equity
    
    # Exit plan parameters (short TTL for scalp)
    STOP_LOSS_PCT = 0.8
    TAKE_PROFIT_PCT = 2.0
    TTL_MS = 5 * 60 * 1000  # 5 minutes
    
    @classmethod
    def generate_intent(
        cls,
        governance: GovernanceContext,
        portfolio: ShadowPortfolio,
        markets: List[MarketSnapshot],
    ) -> StrategyIntent:
        """
        Generate scalp intent with strict liquidity and cost gates.
        
        Returns NOOP if any gate fails, ENTRY if all pass.
        """
        if not markets:
            return cls._create_noop(governance, "No markets available")
        
        market = markets[0]
        
        # Gate 1: Governance blocks
        governance_block = cls._check_governance_blocks(governance)
        if governance_block:
            return cls._create_noop(governance, governance_block)
        
        # Gate 2: Volatility filter (ELEVATED only for breakouts)
        if market.volatility_state != VolatilityState.ELEVATED:
            return cls._create_noop(
                governance,
                f"Volatility gate: state={market.volatility_state.value} (need ELEVATED)"
            )
        
        # Gate 3: Liquidity gate (strict for scalp)
        if market.spread_pct > cls.MAX_SPREAD_PCT:
            return cls._create_noop(
                governance,
                f"Liquidity gate: spread_pct={market.spread_pct:.6f} > threshold={cls.MAX_SPREAD_PCT:.6f}"
            )
        
        # Calculate expected move (target at least 0.10% or 2x spread)
        expected_move = market.mid * max(market.spread_pct * 2.0, 0.0010)
        
        # Calculate estimated cost
        estimated_cost = cls._estimate_cost(market)
        
        # Gate 4: Aggressive cost gate (K=1.5)
        if expected_move < 1.5 * estimated_cost:
            return cls._create_noop(
                governance,
                f"Cost Gate: expected_move={expected_move:.8f} < 1.5*estimated_cost={1.5*estimated_cost:.8f}"
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
        """Estimate total execution cost for scalp (deterministic)."""
        # Spread cost
        estimated_spread = market.mid * market.spread_pct
        
        # Slippage + fee
        estimated_slip_fee = market.mid * ((cls.SLIP_BPS + cls.FEE_BPS) / 10000.0)
        
        return estimated_spread + estimated_slip_fee
    
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
        
        # Calculate size (1% of equity for scalp)
        size_base = (portfolio.equity * cls.SIZE_FRACTION) / market.mid
        
        # Exit plan with tight SL/TP + short TTL
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
            f"Breakout Scalp: vol_state={market.volatility_state.value} | "
            f"spread_pct={market.spread_pct:.6f} | "
            f"expected_move={expected_move:.8f} | "
            f"estimated_cost={estimated_cost:.8f} | "
            f"ratio={expected_move/estimated_cost:.2f}x | "
            f"Liquidity PASS | Cost Gate PASS (K=1.5)"
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
            confidence=0.75,
            rationale=rationale,
            strategy_id=cls.STRATEGY_ID,
            strategy_frequency=StrategyFrequency.SCALP,
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
            strategy_frequency=StrategyFrequency.SCALP,
        )
    
    @staticmethod
    def _generate_intent_id(correlation_id: str, ts_ms: int, intent_type: str) -> str:
        """Generate deterministic intent ID."""
        payload = f"{correlation_id}:{ts_ms}:breakout_scalp_v1:{intent_type}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
