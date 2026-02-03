"""E5.1 Preflight Config - Normalization policy settings"""
from decimal import Decimal
from pydantic import BaseModel

class PreflightConfig(BaseModel):
    """
    Configuration for execution preflight normalization
    
    LOCKED DEFAULTS:
    - strict_batch_mode = True (fail-all-or-none)
    - cap_reapplication_forbidden = True (mechanical quantization only)
    - allow_generated_intent_id = False (identity from E4 required)
    """
    
    # Batch behavior
    strict_batch_mode:bool=True  # Any failure blocks all
    
    # Identity
    allow_generated_intent_id:bool=False  # Force E4 identity
    
    # Decimal precision
    decimal_precision:int=28
    
    # Constraint freshness
    constraint_staleness_ms:int=3600000  # 1 hour
    
    # Quantization
    quantize_market_orders:bool=True
    quantize_limit_price:bool=True
    
    # Business logic prohibition (LOCKED)
    cap_reapplication_forbidden:bool=True  # No sizing logic in preflight
    
    class Config:
        json_encoders={Decimal:str}
