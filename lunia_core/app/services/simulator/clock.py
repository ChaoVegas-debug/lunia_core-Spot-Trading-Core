"""E5 Deterministic Simulation Clock - Seeded, reproducible time"""
import time
from typing import Optional

class DeterministicSimClock:
    """
    Deterministic clock for simulation replay
    
    Features:
    - Seeded start time
    - Manual advance for testing
    - Reproducible across runs
    - Latency simulation
    """
    
    def __init__(self,seed_ms:Optional[int]=None,latency_ms:int=0):
        self.current_ms=seed_ms if seed_ms is not None else int(time.time()*1000)
        self.latency_ms=latency_ms
        self.event_counter=0
    
    def now_ms(self)->int:
        """Get current simulated time"""
        return self.current_ms
    
    def advance(self,delta_ms:int):
        """Advance clock by delta (for testing)"""
        self.current_ms+=delta_ms
    
    def next_event_time(self)->int:
        """Get time for next event (with latency)"""
        self.event_counter+=1
        return self.current_ms+self.latency_ms
    
    def reset(self,seed_ms:Optional[int]=None):
        """Reset clock to seed"""
        self.current_ms=seed_ms if seed_ms is not None else int(time.time()*1000)
        self.event_counter=0
