"""
Epoch 9.4: Trend Following Strategy (EMA Crossover)

Features:
- EMA crossover logic (Fast > Slow → BUY)
- Cold-start handling (returns None until warmed)
- Regime gating (TREND, BREAKOUT, UNKNOWN only)
- Volatility filtering (rejects HIGH volatility)

Governance:
- Deterministic (no randomness)
- Snapshot-only (no external state)
- Fail-safe (returns None on uncertainty)
"""
from typing import Optional, List
from collections import deque

from ..governance import GovernedStrategy, StrategyDescriptor, StrategyClassification, RiskProfile
from ..models import StrategyContext, IntentProposal, SignalSide


class TrendFollowingStrategy(GovernedStrategy):
    """
    EMA Crossover Strategy
    
    Logic: Fast EMA (12) > Slow EMA (26) → BUY
    
    Cold-Start: Requires min 26 samples before emitting signals
    """
    
    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        min_confidence: float = 0.6
    ):
        """Initialize with EMA parameters"""
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.min_confidence = min_confidence
        
        # Internal state (circular buffer for prices)
        self._price_history: deque = deque(maxlen=slow_period)
        
        # Governance descriptor
        self._descriptor = StrategyDescriptor(
            id="trend_following_ema",
            name="Trend Following (EMA Crossover)",
            version="1.0.0",
            classification=StrategyClassification.CONTEXT_AWARE,
            risk_profile=RiskProfile.RISKY,
            allowed_regimes=["TREND", "BREAKOUT", "UNKNOWN"],
            required_market_state_fields=["volatility.vol_regime", "regime.regime"],
            ai_execution_allowed=False
        )
        
        # Validate at init
        self._descriptor.validate()
    
    @property
    def descriptor(self) -> StrategyDescriptor:
        """Return governance descriptor"""
        return self._descriptor
    
    def evaluate(self, context: StrategyContext) -> Optional[IntentProposal]:
        """
        Evaluate strategy and return intent (or None)
        
        Cold-start: Returns None until warmed up
        """
        # Get current price
        price = context.market_snapshot.get("close", 0.0)
        if price <= 0:
            return None  # No valid price
        
        # Update price history
        self._price_history.append(price)
        
        # COLD-START CHECK: Need full window
        if len(self._price_history) < self.slow_period:
            return None  # Still warming up (implicit reason: WARMING_UP)
        
        # Calculate EMAs
        fast_ema = self._calculate_ema(self.fast_period)
        slow_ema = self._calculate_ema(self.slow_period)
        
        if fast_ema is None or slow_ema is None:
            return None
        
        # Check regime
        regime = context.get_market_regime()
        if regime not in self._descriptor.allowed_regimes:
            return None  # Regime not allowed
        
        # Check volatility (FORBIDDEN: HIGH)
        vol_regime = context.get_volatility_regime()
        if vol_regime == "HIGH":
            return None  # Too risky
        
        # Check market risk flag
        market_risk = context.get_market_risk_flag()
        if market_risk == "DANGEROUS":
            return None  # Market too dangerous
        
        # Determine signal
        if fast_ema > slow_ema:
            # Uptrend → BUY
            spread_pct = (fast_ema - slow_ema) / slow_ema
            confidence = min(0.95, self.min_confidence + spread_pct * 2)
            
            return IntentProposal(
                symbol=context.symbol,
                strategy_id=self._descriptor.id,
                side=SignalSide.BUY,
                signal_strength=confidence,
                rationale=f"EMA crossover: fast={fast_ema:.2f} > slow={slow_ema:.2f} (regime={regime}, vol={vol_regime})"
            )
        elif fast_ema < slow_ema * 0.98:  # Significant downtrend
            # Downtrend → SELL
            spread_pct = (slow_ema - fast_ema) / slow_ema
            confidence = min(0.95, self.min_confidence + spread_pct * 2)
            
            return IntentProposal(
                symbol=context.symbol,
                strategy_id=self._descriptor.id,
                side=SignalSide.SELL,
                signal_strength=confidence,
                rationale=f"EMA crossover: fast={fast_ema:.2f} < slow={slow_ema:.2f} (regime={regime}, vol={vol_regime})"
            )
        else:
            # Neutral → HOLD
            return IntentProposal(
                symbol=context.symbol,
                strategy_id=self._descriptor.id,
                side=SignalSide.HOLD,
                signal_strength=0.5,
                rationale=f"EMA neutral: fast={fast_ema:.2f} ≈ slow={slow_ema:.2f}"
            )
    
    def _calculate_ema(self, period: int) -> Optional[float]:
        """Calculate EMA for given period"""
        if len(self._price_history) < period:
            return None
        
        # Simple EMA calculation
        multiplier = 2.0 / (period + 1)
        prices = list(self._price_history)[-period:]
        
        # Start with SMA
        ema = sum(prices) / len(prices)
        
        # Apply EMA formula
        for price in prices[1:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
