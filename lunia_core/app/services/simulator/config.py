"""E5 Simulator Config - Fee/slippage/latency models"""
from decimal import Decimal
from pydantic import BaseModel

class SimulatorConfig(BaseModel):
    """Configuration for simulated exchange behavior"""
    
    # Fees
    taker_fee_pct:Decimal=Decimal("0.001")  # 0.1% default
    maker_fee_pct:Decimal=Decimal("0.001")
    
    # Slippage (simple model for now)
    slippage_bps:Decimal=Decimal("0")  # Basis points
    
    # Latency
    latency_ms:int=0  # Deterministic by default
    
    # Strictness
    rejection_strictness:str="STRICT"  # Always strict in tests
    
    # Decimal precision
    decimal_precision:int=28
    
    # Constraint staleness threshold
    constraint_staleness_ms:int=3600000  # 1 hour
    
    class Config:
        json_encoders={Decimal:str}
