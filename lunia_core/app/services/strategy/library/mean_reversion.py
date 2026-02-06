"""
Epoch 9.4: Mean Reversion Strategy (Bollinger Bands)

Features:
- Bollinger Bands logic (Price < Lower Band → BUY)
- Cold-start handling (requires full window for mean/std)
- Regime gating (RANGE only)
- Liquidity filtering (rejects wide spreads)
"""
from typing import Optional
from collections import deque
import math

from ..governance import GovernedStrategy, StrategyDescriptor, StrategyClassification, RiskProfile
from ..models import StrategyContext, IntentProposal, SignalSide


class MeanReversionStrategy(GovernedStrategy):
    """
    Bollinger Bands Mean Reversion
    
    Logic: Price < Lower Band → BUY, Price > Upper Band → SELL
    
    Cold-Start: Requires min 20 samples for statistics
    """
    
    def __init__(self, period: int = 20, std_multiplier: float = 2.0):
        self.period = period
        self.std_multiplier = std_multiplier
        self._price_history: deque = deque(maxlen=period)
        
        self._descriptor = StrategyDescriptor(
            id="mean_reversion_bb",
            name="Mean Reversion (Bollinger Bands)",
            version="1.0.0",
            classification=StrategyClassification.CONTEXT_AWARE,
            risk_profile=RiskProfile.SAFE,
            allowed_regimes=["RANGE"],
            required_market_state_fields=["liquidity.spread_pct", "liquidity.liquidity_stress"],
            ai_execution_allowed=False
        )
        self._descriptor.validate()
    
    @property
    def descriptor(self) -> StrategyDescriptor:
        return self._descriptor
    
    def evaluate(self, context: StrategyContext) -> Optional[IntentProposal]:
        price = context.market_snapshot.get("close", 0.0)
        if price <= 0:
            return None
        
        self._price_history.append(price)
        
        # COLD-START: Need full window
        if len(self._price_history) < self.period:
            return None  # WARMING_UP
        
        # Check regime (RANGE only)
        regime = context.get_market_regime()
        if regime != "RANGE":
            return None
        
        # Check liquidity (FORBIDDEN: wide spreads)
        spread_pct = context.market_state.get("liquidity", {}).get("spread_pct", 0.0)
        if spread_pct > 0.001:  # 0.1%
            return None
        
        liquidity_stress = context.get_liquidity_stress()
        if liquidity_stress == "CRITICAL":
            return None
        
        # Calculate Bollinger Bands
        prices = list(self._price_history)
        mean = sum(prices) / len(prices)
        variance = sum((p - mean) ** 2 for p in prices) / len(prices)
        std = math.sqrt(variance)
        
        upper_band = mean + (self.std_multiplier * std)
        lower_band = mean - (self.std_multiplier * std)
        
        # Determine signal
        if price < lower_band:
            # Oversold → BUY
            distance_pct = (lower_band - price) / mean
            confidence = min(0.9, 0.6 + distance_pct * 5)
            
            return IntentProposal(
                symbol=context.symbol,
                strategy_id=self._descriptor.id,
                side=SignalSide.BUY,
                signal_strength=confidence,
                rationale=f"Oversold: price={price:.2f} < lower_band={lower_band:.2f} (mean={mean:.2f})"
            )
        elif price > upper_band:
            # Overbought → SELL
            distance_pct = (price - upper_band) / mean
            confidence = min(0.9, 0.6 + distance_pct * 5)
            
            return IntentProposal(
                symbol=context.symbol,
                strategy_id=self._descriptor.id,
                side=SignalSide.SELL,
                signal_strength=confidence,
                rationale=f"Overbought: price={price:.2f} > upper_band={upper_band:.2f} (mean={mean:.2f})"
            )
        else:
            # Within bands → HOLD
            return IntentProposal(
                symbol=context.symbol,
                strategy_id=self._descriptor.id,
                side=SignalSide.HOLD,
                signal_strength=0.4,
                rationale=f"Within bands: {lower_band:.2f} < {price:.2f} < {upper_band:.2f}"
            )
