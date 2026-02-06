"""
Epoch 9.4: Breakout Confirmation Strategy (Price + Volume)

Features:
- Breakout + volume spike confirmation
- Cold-start handling (requires volume history)
- Regime gating (BREAKOUT, TREND)
- Volume data requirement (degrades if missing)
"""
from typing import Optional
from collections import deque

from ..governance import GovernedStrategy, StrategyDescriptor, StrategyClassification, RiskProfile
from ..models import StrategyContext, IntentProposal, SignalSide


class BreakoutConfirmationStrategy(GovernedStrategy):
    """
    Breakout + Volume Confirmation
    
    Logic: Price breakout + volume.rel_volume > 1.5 → BUY
    
    Cold-Start: Requires volume history
    """
    
    def __init__(self, volume_threshold: float = 1.5, lookback: int = 10):
        self.volume_threshold = volume_threshold
        self.lookback = lookback
        self._price_history: deque = deque(maxlen=lookback)
        
        self._descriptor = StrategyDescriptor(
            id="breakout_confirmation",
            name="Breakout Confirmation (Price + Volume)",
            version="1.0.0",
            classification=StrategyClassification.CONTEXT_AWARE,
            risk_profile=RiskProfile.RISKY,
            allowed_regimes=["BREAKOUT", "TREND"],
            required_market_state_fields=["volume.rel_volume"],
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
        
        # COLD-START: Need history
        if len(self._price_history) < self.lookback:
            return None  # WARMING_UP
        
        # Check regime
        regime = context.get_market_regime()
        if regime not in self._descriptor.allowed_regimes:
            return None
        
        # Check market risk
        if context.get_market_risk_flag() == "DANGEROUS":
            return None
        
        # Check volume data (REQUIRED)
        rel_volume = context.market_state.get("volume", {}).get("rel_volume")
        if rel_volume is None:
            return None  # Missing required data
        
        # Calculate resistance (recent high)
        prices = list(self._price_history)[:-1]  # Exclude current
        resistance = max(prices) if prices else price
        
        # Breakout detection
        if price > resistance * 1.02 and rel_volume > self.volume_threshold:
            # Breakout + volume confirmation → BUY
            breakout_pct = (price - resistance) / resistance
            confidence = min(0.95, 0.7 + breakout_pct * 10)
            
            return IntentProposal(
                symbol=context.symbol,
                strategy_id=self._descriptor.id,
                side=SignalSide.BUY,
                signal_strength=confidence,
                rationale=f"Breakout confirmed: price={price:.2f} > resistance={resistance:.2f}, vol={rel_volume:.2f}x"
            )
        elif price < min(prices) * 0.98 and rel_volume > self.volume_threshold:
            # Breakdown + volume → SELL
            breakdown_pct = (min(prices) - price) / min(prices)
            confidence = min(0.95, 0.7 + breakdown_pct * 10)
            
            return IntentProposal(
                symbol=context.symbol,
                strategy_id=self._descriptor.id,
                side=SignalSide.SELL,
                signal_strength=confidence,
                rationale=f"Breakdown confirmed: price={price:.2f} < support={min(prices):.2f}, vol={rel_volume:.2f}x"
            )
        else:
            # No breakout → HOLD
            return IntentProposal(
                symbol=context.symbol,
                strategy_id=self._descriptor.id,
                side=SignalSide.HOLD,
                signal_strength=0.3,
                rationale=f"No breakout: price={price:.2f}, vol={rel_volume:.2f}x"
            )
