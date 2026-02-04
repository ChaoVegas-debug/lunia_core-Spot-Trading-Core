"""Genesis Data Seeder - Deterministic synthetic price generator for EPOCH F"""
import random
import math
from decimal import Decimal
from typing import List
from lunia_core.app.services.history.models import HistoricalTick

class GenesisDataSeeder:
    """
    Deterministic synthetic price generator
    
    Features:
    - Trend (linear drift)
    - Sine wave (periodic oscillation)
    - Bounded seeded noise (deterministic)
    - Guarantees EMA(10/30) crossovers
    
    LOCKED CONFIG:
    - Symbol: GENESIS-BTC
    - Bars: 1000
    - Timeframe: 1m (60000ms)
    - Seed: GENESIS_SEED=1337
    - Start: SIM_CLOCK_SEED_MS=1700000000000
    """
    
    def __init__(self,seed:int=1337,start_ms:int=1700000000000):
        self.seed=seed
        self.start_ms=start_ms
        self.rng=random.Random(seed)
        
        # Price model parameters (tuned for crossovers)
        self.base_price=50000.0
        self.trend_slope=5.0  # +5 per bar
        self.sine_amplitude=500.0
        self.sine_period=100  # bars
        self.noise_amplitude=50.0
    
    def generate_bars(self,count:int=1000)->List[HistoricalTick]:
        """Generate deterministic synthetic bars"""
        ticks=[]
        
        for i in range(count):
            # Timestamp (1m cadence)
            timestamp_ms=self.start_ms+(i*60000)
            
            # Price components
            trend=self.trend_slope*i
            sine=self.sine_amplitude*math.sin(2*math.pi*i/self.sine_period)
            noise=self.noise_amplitude*(self.rng.random()-0.5)*2  # Bounded [-amplitude, +amplitude]
            
            # Mid price
            mid_price=self.base_price+trend+sine+noise
            
            # Bid/ask spread (0.01% typical)
            spread=mid_price*0.0001
            bid=mid_price-spread/2
            ask=mid_price+spread/2
            
            tick=HistoricalTick(
                symbol="GENESIS-BTC",
                timestamp_ms=timestamp_ms,
                mid_price=mid_price,
                bid=bid,
                ask=ask,
                snapshot_version=i+1,  # Monotonic
                source_snapshot_id=f"genesis_{i}",
                ingested_at_ms=timestamp_ms
            )
            ticks.append(tick)
        
        return ticks
    
    def seed_to_d2(self,store,count:int=1000)->tuple[int,int]:
        """
        Seed data to D2 store (idempotent)
        
        Returns: (ticks_generated, ticks_appended)
        """
        ticks=self.generate_bars(count)
        appended_count=0
        
        for tick in ticks:
            result=store.append_tick(tick)
            if result.ok:
                appended_count+=1
        
        return (len(ticks),appended_count)
