"""Genesis EMA Crossover Strategy - Minimal, deterministic, hard-coded (EPOCH F)"""
from decimal import Decimal
from typing import Optional,List
from app.services.strategy.models import IntentProposal,SignalSide,StrategyContext
from app.services.history.models import HistoricalTick

class GenesisEMAStrategy:
    """
    Minimal EMA crossover strategy (10/30)
    
    Rules:
    - fast > slow AND flat → BUY
    - fast < slow AND long → SELL/EXIT
    
    LOCKED:
    - Fast EMA: 10
    - Slow EMA: 30
    - No optimization
    - No lookahead
    - One position at a time
    - Deterministic bar-by-bar
    """
    
    def __init__(self,fast_period:int=10,slow_period:int=30):
        self.fast_period=fast_period
        self.slow_period=slow_period
        self.price_history:List[float]=[]
        self.position:Optional[str]=None  # None=flat, "LONG"=long
    
    def _calculate_ema(self,prices:List[float],period:int)->Optional[float]:
        """Calculate EMA (simple implementation)"""
        if len(prices)<period:
            return None
        
        # Use SMA for first value
        sma=sum(prices[:period])/period
        multiplier=2/(period+1)
        
        ema=sma
        for price in prices[period:]:
            ema=(price-ema)*multiplier+ema
        
        return ema
    
    def update_position(self,pos:Optional[str]):
        """Update position state"""
        self.position=pos
    
    def evaluate(
        self,
        tick:HistoricalTick,
        snapshot_version:int
    )->Optional[IntentProposal]:
        """
        Evaluate bar and generate signal
        
        Returns: IntentProposal or None
        """
        # Update history
        self.price_history.append(tick.mid_price)
        
        # Calculate EMAs
        ema_fast=self._calculate_ema(self.price_history,self.fast_period)
        ema_slow=self._calculate_ema(self.price_history,self.slow_period)
        
        # Need both EMAs
        if ema_fast is None or ema_slow is None:
            return None
        
        # Signal logic
        signal=None
        rationale=""
        
        if ema_fast>ema_slow and self.position is None:
            # BUY signal
            signal=SignalSide.BUY
            rationale=f"EMA crossover BUY: fast={ema_fast:.2f} > slow={ema_slow:.2f}, position=flat"
        
        elif ema_fast<ema_slow and self.position=="LONG":
            # SELL/EXIT signal
            signal=SignalSide.SELL
            rationale=f"EMA crossover SELL: fast={ema_fast:.2f} < slow={ema_slow:.2f}, position=long"
        
        if signal is None:
            return None
        
        # Generate IntentProposal
        proposal=IntentProposal(
            strategy_id="genesis_ema_10_30",
            symbol=tick.symbol,
            side=signal,
            signal_strength=abs(ema_fast-ema_slow)/ema_slow,  # Normalized strength
            reference_price=tick.mid_price,
            rationale=rationale,
            governance_metadata={
                "ema_fast":ema_fast,
                "ema_slow":ema_slow,
                "bar_timestamp_ms":tick.timestamp_ms,
                "snapshot_version":snapshot_version
            }
        )
        
        return proposal
