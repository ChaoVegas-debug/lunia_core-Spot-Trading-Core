"""
Epoch 9.1: Context-Aware Momentum Strategy (First-Citizen Reference Implementation)

This is a REFERENCE IMPLEMENTATION demonstrating:
- GovernedStrategy protocol compliance
- StrategyDescriptor metadata contract
- Deterministic market_state consumption
- Graceful degradation when market_state is missing
- Deterministic reasoning for audit trail

Strategy Logic:
- Calculates momentum based on bid-ask positioning
- Adjusts threshold based on volatility regime (Phase 8.3 market_state)
- Only operates in RANGE/TREND regimes (not BREAKOUT)
- Refuses to trade in HIGH volatility or DANGEROUS market conditions
- Provides complete audit trail via deterministic_reasoning()

Classification: CONTEXT_AWARE (consumes market_state deterministically)
Risk Profile: SAFE (conservative, low volatility tolerance)
"""
from typing import Optional, Union

from ..governance import (
    GovernedStrategy,
    StrategyDescriptor,
    StrategyClassification,
    RiskProfile
)
from ..models import StrategyContext, IntentProposal, SignalSide


class ContextMomentumStrategy(GovernedStrategy):
    """
    First-Citizen Governed Strategy: Context-Aware Momentum
    
    Deterministic logic that consumes market_state to adjust signal thresholds.
    
    Operating Rules:
    - Buy if price momentum > threshold AND volatility regime is LOW/MEDIUM
    - Sell if price momentum < -threshold
    - Threshold adjusts based on volatility (higher vol = higher threshold)
    - Refuses to trade in HIGH volatility or DANGEROUS market_risk
    - Requires RANGE or TREND market regime
    
    Certification:
    - Allowed regimes: RANGE, TREND
    - Max volatility: MEDIUM
    - Liquidity tolerance: NORMAL
    - AI shadow: enabled
    - AI execution: FORBIDDEN
    """
    
    def __init__(self):
        """Initialize strategy with metadata contract"""
        self._descriptor = StrategyDescriptor(
            strategy_id="context_momentum_v1",
            version="1.0.0",
            classification=StrategyClassification.CONTEXT_AWARE,
            risk_profile=RiskProfile.SAFE,
            required_market_state_fields=frozenset([
                "volatility.vol_regime",
                "volatility.atr",
                "regime.regime",
                "market_risk_flag"
            ]),
            allowed_market_regimes=frozenset(["RANGE", "TREND"]),
            max_volatility_regime="MEDIUM",
            liquidity_tolerance="NORMAL",
            ai_shadow_enabled=True,
            ai_execution_allowed=False
        )
        
        # Validate descriptor integrity
        self._descriptor.validate()
    
    @property
    def descriptor(self) -> StrategyDescriptor:
        """Strategy metadata contract"""
        return self._descriptor
    
    def evaluate(self, context: StrategyContext) -> Optional[IntentProposal]:
        """
        Deterministic evaluation logic.
        
        Flow:
        1. Calculate momentum (bid-ask positioning)
        2. Get market state (volatility regime, market regime, risk flag)
        3. Determine threshold based on volatility
        4. Check operating boundaries (regime, volatility, risk)
        5. Generate signal if momentum exceeds threshold
        
        Args:
            context: Strategy context (snapshot + market_state)
        
        Returns:
            IntentProposal if signal generated, None otherwise
        """
        # Calculate momentum (simplified)
        momentum = self._calculate_momentum(context)
        
        # Get market state (safe accessors - graceful degradation)
        vol_regime = context.get_volatility_regime()
        market_regime = context.get_market_regime()
        market_risk = context.get_market_risk_flag()
        atr = context.get_atr()
        
        # SAFETY CHECK: Refuse to trade in dangerous conditions
        if market_risk == "DANGEROUS":
            return None  # No signal in dangerous markets
        
        if vol_regime == "HIGH":
            return None  # No signal in high volatility
        
        if market_regime not in ["RANGE", "TREND", "UNKNOWN"]:
            return None  # Only trade in RANGE/TREND (or UNKNOWN as fallback)
        
        # Adjust threshold based on volatility
        base_threshold = 0.01  # 1% momentum threshold
        
        if vol_regime == "MEDIUM":
            threshold = base_threshold * 1.5  # 50% more conservative in medium vol
        elif vol_regime == "LOW":
            threshold = base_threshold
        else:  # UNKNOWN
            threshold = base_threshold * 2.0  # Very conservative when unknown
        
        # Decision logic
        if momentum > threshold:
            return IntentProposal(
                strategy_id=self.descriptor.strategy_id,
                symbol=context.symbol,
                side=SignalSide.BUY,
                signal_strength=min(momentum / threshold, 1.0),  # Normalize to 0-1
                reference_price=context.snapshot.mid_price,
                rationale=self.deterministic_reasoning(context, "BUY"),
                governance_metadata={
                    "momentum": momentum,
                    "threshold": threshold,
                    "vol_regime": vol_regime,
                    "market_regime": market_regime,
                    "market_risk": market_risk
                }
            )
        elif momentum < -threshold:
            return IntentProposal(
                strategy_id=self.descriptor.strategy_id,
                symbol=context.symbol,
                side=SignalSide.SELL,
                signal_strength=min(abs(momentum) / threshold, 1.0),
                reference_price=context.snapshot.mid_price,
                rationale=self.deterministic_reasoning(context, "SELL"),
                governance_metadata={
                    "momentum": momentum,
                    "threshold": threshold,
                    "vol_regime": vol_regime,
                    "market_regime": market_regime,
                    "market_risk": market_risk
                }
            )
        
        return None  # No signal
    
    def deterministic_reasoning(
        self,
        context: StrategyContext,
        intent: Optional[Union[str, IntentProposal]]
    ) -> str:
        """
        Human-readable explanation of core logic decision.
        
        This is the strategy's OWN explanation, NOT AI-generated.
        Used for audit trail and AI comparison.
        
        Args:
            context: Strategy context
            intent: Result from evaluate() or "BUY"/"SELL" string
        
        Returns:
            Human-readable explanation
        """
        momentum = self._calculate_momentum(context)
        vol_regime = context.get_volatility_regime()
        market_regime = context.get_market_regime()
        market_risk = context.get_market_risk_flag()
        atr = context.get_atr()
        
        # Determine signal type
        if intent is None:
            signal_type = "NONE"
        elif isinstance(intent, str):
            signal_type = intent
        else:
            signal_type = intent.side.value
        
        # Build reasoning
        if signal_type == "NONE":
            if market_risk == "DANGEROUS":
                return f"NO SIGNAL: Dangerous market conditions (risk={market_risk})"
            elif vol_regime == "HIGH":
                return f"NO SIGNAL: High volatility regime (vol={vol_regime})"
            elif market_regime not in ["RANGE", "TREND", "UNKNOWN"]:
                return f"NO SIGNAL: Unsupported market regime (regime={market_regime})"
            else:
                return (
                    f"NO SIGNAL: Momentum below threshold "
                    f"(momentum={momentum:.4f}, vol_regime={vol_regime}, "
         f"market_regime={market_regime}, risk={market_risk})"
                )
        else:
            return (
                f"{signal_type} SIGNAL: momentum={momentum:.4f}, "
                f"vol_regime={vol_regime}, market_regime={market_regime}, "
                f"risk={market_risk}, atr={atr if atr else 'N/A'}, "
                f"threshold_adjusted_for_volatility=True"
            )
    
    def _calculate_momentum(self, context: StrategyContext) -> float:
        """
        Calculate momentum based on bid-ask positioning.
        
        Simplified momentum proxy:
        - If ask > mid > bid (healthy spread), use normalized distance
        - Positive momentum = price near ask (buying pressure)
        - Negative momentum = price near bid (selling pressure)
        
        Args:
            context: Strategy context
        
        Returns:
            Momentum value (can be positive or negative)
        
        Note:
            In production, this would use historical price data.
            For demo, we use spread positioning as a proxy.
        """
        bid = context.snapshot.bid
        ask = context.snapshot.ask
        mid = context.snapshot.mid_price
        
        if not bid or not ask or not mid or mid <= 0:
            return 0.0  # Invalid data
        
        spread = ask - bid
        if spread <= 0:
            return 0.0  # Invalid spread
        
        # Normalized distance from mid to ask
        # If mid is near ask → positive momentum (buying pressure)
        # If mid is near bid → negative momentum (selling pressure)
        momentum = (mid - (bid + ask) / 2) / mid
        
        return momentum
