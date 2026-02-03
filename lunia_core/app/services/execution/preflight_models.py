"""E5.1 Execution Preflight Models - Normalized orders (renamed from models.py collision)"""
from decimal import Decimal
from typing import Optional,Dict,List
from enum import Enum
from pydantic import BaseModel,Field

class PreflightRejectionReason(str,Enum):
    """Explicit preflight rejection reasons"""
    MISSING_INTENT_ID="MISSING_INTENT_ID"
    MISSING_CONSTRAINTS="MISSING_CONSTRAINTS"
    STALE_CONSTRAINTS="STALE_CONSTRAINTS"
    INVALID_PRICE="INVALID_PRICE"
    QTY_NOT_ALIGNED_TO_STEP="QTY_NOT_ALIGNED_TO_STEP"
    PRICE_NOT_ALIGNED_TO_TICK="PRICE_NOT_ALIGNED_TO_TICK"
    MIN_QTY_NOT_MET="MIN_QTY_NOT_MET"
    MAX_QTY_EXCEEDED="MAX_QTY_EXCEEDED"
    MIN_NOTIONAL_NOT_MET="MIN_NOTIONAL_NOT_MET"
    MIXED_SNAPSHOT_BATCH="MIXED_SNAPSHOT_BATCH"
    FLOAT_DETECTED="FLOAT_DETECTED"
    NON_FINITE_DECIMAL="NON_FINITE_DECIMAL"
    CAP_REAPPLICATION_FORBIDDEN="CAP_REAPPLICATION_FORBIDDEN"

class NormalizedOrder(BaseModel):
    """
    Preflight-normalized order guaranteed to pass E5 Holodeck
    
    INVARIANTS:
    - Decimal-only (no float)
    - Quantized (FLOOR to step/tick)
    - Identity contract satisfied
    - Constraints validated
    - Complete audit trail
    """
    # Identity
    intent_id:str
    intent_id_source:str
    
    # Order details
    symbol:str
    side:str  # BUY/SELL
    order_type:str="LIMIT"  # LIMIT/MARKET
    
    # Quantities (Decimal + canonical string)
    qty_decimal:Decimal
    qty_decimal_str:str  # Canonical for exchange
    price_decimal:Optional[Decimal]=None
    price_decimal_str:Optional[str]=None
    notional_decimal:Decimal
    
    # Snapshot consistency
    snapshot_version:int
    now_ms:int
    
    # Constraints provenance
    constraints_provenance:Dict=Field(default_factory=dict)
    
    # Audit metadata
    metadata:Dict=Field(default_factory=dict)
    
    class Config:
        frozen=True
        json_encoders={Decimal:str}

class PreflightResult(BaseModel):
    """Result of single order preflight"""
    ok:bool
    normalized_order:Optional[NormalizedOrder]=None
    rejection_reason:Optional[PreflightRejectionReason]=None
    rejection_details:Optional[str]=None
    metadata:Dict=Field(default_factory=dict)
    
    class Config:
        json_encoders={Decimal:str}

class BatchPreflightResult(BaseModel):
    """Result of batch preflight"""
    ok:bool
    normalized_orders:List[NormalizedOrder]=Field(default_factory=list)
    blocking_reasons:List[str]=Field(default_factory=list)
    metadata:Dict=Field(default_factory=dict)
    
    class Config:
        json_encoders={Decimal:str}
