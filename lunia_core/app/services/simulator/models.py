"""E5 Simulator Models - Frozen, immutable, Decimal-only"""
from decimal import Decimal
from typing import Optional,Dict
from enum import Enum
from pydantic import BaseModel,Field

class RejectionReason(str,Enum):
    """Explicit rejection reasons (exchange-like)"""
    QTY_NOT_ALIGNED_TO_STEP="QTY_NOT_ALIGNED_TO_STEP"
    PRICE_NOT_ALIGNED_TO_TICK="PRICE_NOT_ALIGNED_TO_TICK"
    MIN_NOTIONAL_NOT_MET="MIN_NOTIONAL_NOT_MET"
    MIN_QTY_NOT_MET="MIN_QTY_NOT_MET"
    MAX_QTY_EXCEEDED="MAX_QTY_EXCEEDED"
    MISSING_INTENT_ID="MISSING_INTENT_ID"
    STALE_CONSTRAINTS="STALE_CONSTRAINTS"
    INVALID_SYMBOL="INVALID_SYMBOL"
    INSUFFICIENT_BALANCE="INSUFFICIENT_BALANCE"
    MIXED_SNAPSHOT_BATCH="MIXED_SNAPSHOT_BATCH"
    FLOAT_DETECTED="FLOAT_DETECTED"

class SimulatedOrder(BaseModel):
    """Order submitted to simulated exchange"""
    order_id:str
    intent_id:str
    intent_id_source:str  # Identity contract
    symbol:str
    side:str  # "BUY" or "SELL"
    qty:Decimal
    price:Optional[Decimal]=None  # None for MARKET
    order_type:str="LIMIT"  # LIMIT/MARKET
    snapshot_version:int
    submitted_at_ms:int
    
    class Config:
        frozen=True
        json_encoders={Decimal:str}

class FillEvent(BaseModel):
    """Fill event from exchange"""
    order_id:str
    fill_id:str
    filled_qty:Decimal
    fill_price:Decimal
    fee:Decimal
    fee_asset:str="USDT"
    filled_at_ms:int
    is_partial:bool=False
    
    class Config:
        frozen=True
        json_encoders={Decimal:str}

class ExecutionReport(BaseModel):
    """Exchange execution report"""
    order_id:str
    accepted:bool
    rejection_reason:Optional[RejectionReason]=None
    rejection_details:Optional[str]=None
    fills:list[FillEvent]=Field(default_factory=list)
    total_filled_qty:Decimal=Decimal("0")
    remaining_qty:Decimal=Decimal("0")
    status:str="NEW"  # NEW/PARTIAL/FILLED/REJECTED
    metadata:Dict=Field(default_factory=dict)
    
    class Config:
        frozen=True
        json_encoders={Decimal:str}
