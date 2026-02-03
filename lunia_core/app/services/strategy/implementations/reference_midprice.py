"""
EPOCH E Phase E1.1: Reference Mid-Price Threshold Strategy
THE FIRST NEURON - Diagnostic probe for pipeline validation
"""
from __future__ import annotations

from typing import Optional

from ..interfaces import IStrategy
from ..models import StrategyContext, IntentProposal, SignalSide


class ReferenceMidPriceThresholdStrategy(IStrategy):
    """
    Reference strategy for pipeline validation
    
    Purpose: Prove the system thinks correctly, not to make profit.
    
    Logic (Deliberately Trivial):
    - Compare current_mid_price with last_seen_mid_price
    - If price moved UP by more than +threshold → propose BUY
    - If price moved DOWN by more than -threshold → propose SELL
    - Otherwise → return None
    - Update last_seen_mid_price deterministically
    
    This strategy validates:
    - State persistence between ticks
    - Version-based triggering
    - Deterministic output
    - Zero execution authority
    
    LOCKED INVARIANTS:
    - Pure function (deterministic)
    - Minimal local state
    - Fail-silent on missing data
    - Zero execution authority
    - Strict state update order
    """
    
    def __init__(self, threshold_pct: float = 0.001):
        """
        Initialize reference strategy
        
        Args:
            threshold_pct: Price movement threshold (default 0.001 = 0.10%)
        """
        self._threshold_pct = threshold_pct
        self._last_mid_price: Optional[float] = None
    
    @property
    def strategy_id(self) -> str:
        return "reference_midprice_v1"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    def on_init(self, context: StrategyContext):
        """
        Initialize strategy (called once at startup)
        
        Args:
            context: Initial strategy context
        """
        # Reset state on initialization
        self._last_mid_price = None
    
    def on_tick(self, context: StrategyContext) -> Optional[IntentProposal]:
        """
        Evaluate strategy on new market data
        
        STRICT ORDER (NON-NEGOTIABLE):
        1. Read current mid price
        2. If first tick → store state, return None
        3. Compute delta
        4. Decide direction
        5. Update state BEFORE returning proposal
        
        Args:
            context: Current strategy context
        
        Returns:
            IntentProposal if threshold breached, None otherwise
        """
        # STEP 1: Read current mid price
        current_mid = context.snapshot.mid_price
        
        # Fail-silent: missing mid price
        if current_mid is None or current_mid <= 0:
            return None
        
        # STEP 2: If first tick → store state, return None
        if self._last_mid_price is None:
            self._last_mid_price = current_mid
            return None
        
        # STEP 3: Compute delta
        delta = current_mid - self._last_mid_price
        delta_pct = delta / self._last_mid_price
        
        # STEP 4: Decide direction
        if delta_pct >= self._threshold_pct:
            # Upward move → BUY signal
            side = SignalSide.BUY
            signal_strength = min(abs(delta_pct) / self._threshold_pct, 1.0)
            rationale = (
                f"Mid price moved +{delta_pct * 100:.4f}% since last tick "
                f"(threshold {self._threshold_pct * 100:.2f}%)"
            )
        elif delta_pct <= -self._threshold_pct:
            # Downward move → SELL signal
            side = SignalSide.SELL
            signal_strength = min(abs(delta_pct) / self._threshold_pct, 1.0)
            rationale = (
                f"Mid price moved {delta_pct * 100:.4f}% since last tick "
                f"(threshold {self._threshold_pct * 100:.2f}%)"
            )
        else:
            # No threshold breach → update state, return None
            self._last_mid_price = current_mid
            return None
        
        # STEP 5: Update state BEFORE returning proposal
        self._last_mid_price = current_mid
        
        # Construct IntentProposal
        return IntentProposal(
            strategy_id=self.strategy_id,
            symbol=context.symbol,
            side=side,
            signal_strength=signal_strength,
            reference_price=current_mid,
            rationale=rationale
        )
    
    def on_stop(self):
        """Cleanup on strategy shutdown"""
        # Reset state
        self._last_mid_price = None
