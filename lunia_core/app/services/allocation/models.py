"""E4 Allocation Models (HARDENED) - Decimal Math, Symbol Constraints, Batch Consistency"""
import time
from decimal import Decimal
from typing import Dict,List,Optional
from pydantic import BaseModel,Field,validator
from enum import Enum
from app.services.strategy.models import SignalSide

class PriceReference(str,Enum):
    MID="MID"
    LAST="LAST"
    LIMIT_PRICE="LIMIT_PRICE"

class CapMode(str,Enum):
    CLAMP="CLAMP"
    BLOCK="BLOCK"

class AllocationConfig(BaseModel):
    max_alloc_per_symbol_pct:Decimal=Field(Decimal("0.20"))
    max_alloc_per_strategy_pct:Optional[Decimal]=None
    min_trade_notional_global:Decimal=Field(Decimal("10.0"))
    strict_mode:bool=True
    cap_mode:CapMode=CapMode.CLAMP
    price_reference:PriceReference=PriceReference.MID
    reserve_buffer_pct:Optional[Decimal]=None
    decimal_precision:int=28
    constraint_staleness_ms:int=3600000  # 1 hour default
    
    @validator('max_alloc_per_symbol_pct','max_alloc_per_strategy_pct','reserve_buffer_pct')
    def validate_pcts(cls,v):
        if v is not None and(v<=0 or v>1):raise ValueError("% must be in (0,1]")
        return v
    
    @validator('min_trade_notional_global')
    def validate_min_notional(cls,v):
        if v<=0:raise ValueError("min_notional must be positive")
        return v


def resolve_intent_id(intent_proposal,now_ms:int,snapshot_version:int)->tuple[str,str,dict]:
    """
    Resolve canonical intent ID with explicit policy
    
    Policy (ordered):
    A) If proposal_id exists → use it
    B) Else if intent_id exists → use it  
    C) Else → generate from (strategy_id, symbol, side, now_ms, snapshot_version)
    
    Returns: (canonical_id, source, metadata)
    """
    # A) Check for proposal_id (preferred)
    if hasattr(intent_proposal,'proposal_id') and intent_proposal.proposal_id:
        return (intent_proposal.proposal_id,"proposal_id",{})
    
    # B) Check for intent_id
    if hasattr(intent_proposal,'intent_id') and intent_proposal.intent_id:
        return (intent_proposal.intent_id,"intent_id",{})
    
    # C) Generate deterministic ID
    generated_id=f"{intent_proposal.strategy_id}_{intent_proposal.symbol}_{intent_proposal.side}_{now_ms}_{snapshot_version}"
    metadata={
        "strategy_id":intent_proposal.strategy_id,
        "symbol":intent_proposal.symbol,
        "side":intent_proposal.side,
        "now_ms":now_ms,
        "snapshot_version":snapshot_version
    }
    return (generated_id,"generated",metadata)

class SymbolConstraints(BaseModel):
    """Per-symbol exchange constraints with provenance"""
    symbol:str
    qty_step_size:Decimal
    min_qty:Optional[Decimal]=None
    max_qty:Optional[Decimal]=None
    min_notional:Optional[Decimal]=None
    tick_size:Optional[Decimal]=None
    source:str="unknown"
    data_timestamp_ms:int
    process_timestamp_ms:int
    
    @validator('qty_step_size')
    def validate_step(cls,v):
        if v<=0:raise ValueError("qty_step_size must be positive")
        return v

class AllocationContext(BaseModel):
    total_equity:Decimal
    locked_margin:Decimal
    reserved_funds:Decimal
    usable_equity:Decimal
    positions:Dict=Field(default_factory=dict)
    mark_prices:Dict[str,Decimal]=Field(default_factory=dict)
    constraints:Dict[str,SymbolConstraints]=Field(default_factory=dict)
    snapshot_version:int

class SizedIntent(BaseModel):
    intent_id:str
    strategy_id:str
    symbol:str
    side:SignalSide
    qty_decimal:Decimal
    qty_decimal_str:str
    notional:Decimal
    price_value_used:Decimal
    price_ref:str
    sizing_policy_id:str
    usable_equity_used:Decimal
    metadata:Dict=Field(default_factory=dict)
    
    class Config:
        frozen=True
        json_encoders={Decimal:str}

class AllocationPlan(BaseModel):
    plan_id:str
    blocked:bool=False
    blocking_reasons:List[str]=Field(default_factory=list)
    sized_intents:List[SizedIntent]=Field(default_factory=list)
    summary_metrics:Dict=Field(default_factory=dict)
    computed_at_ms:int
    snapshot_version:int
    
    class Config:
        frozen=True
        json_encoders={Decimal:str}
