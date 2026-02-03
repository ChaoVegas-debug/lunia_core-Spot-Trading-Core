"""E4 Decimal Math Kernel + Policies (HARDENED) - No float drift, deterministic quantization"""
from decimal import Decimal,getcontext,ROUND_DOWN,InvalidOperation
from typing import Optional
from pydantic import BaseModel

# Set Decimal precision globally
getcontext().prec=28

class PolicyResult(BaseModel):
    ok:bool
    value:Optional[Decimal]=None
    reason:Optional[str]=None
    metadata:dict={}
    
    class Config:
        json_encoders={Decimal:str}

class DecimalMathKernel:
    """Decimal-only math to prevent float drift"""
    
    @staticmethod
    def ensure_context(required_precision:int=28):
        """Ensure Decimal context has sufficient precision (fail-fast)"""
        current=getcontext().prec
        if current<required_precision:
            raise ValueError(f"DECIMAL_PREC_TOO_LOW: required={required_precision}, current={current}")
    
    @staticmethod
    def safe_div(a:Decimal,b:Decimal)->Optional[Decimal]:
        if b==0:return None
        try:
            return a/b
        except InvalidOperation:
            return None
    
    @staticmethod
    def safe_mul(a:Decimal,b:Decimal)->Optional[Decimal]:
        try:
            return a*b
        except InvalidOperation:
            return None
    
    @staticmethod
    def floor_to_step(qty:Decimal,step_size:Decimal)->Decimal:
        """Floor quantization to step_size"""
        if step_size<=0:return Decimal(0)
        return (qty//step_size)*step_size
    
    @staticmethod
    def canonical_decimal_str(qty:Decimal,step_size:Decimal)->str:
        """Deterministic string repr matching step_size scale"""
        scale=abs(step_size.as_tuple().exponent)
        quantized=qty.quantize(Decimal(10)**(-scale),rounding=ROUND_DOWN)
        return str(quantized.normalize())
    
    @staticmethod
    def is_finite(d:Decimal)->bool:
        return d.is_finite() and not d.is_nan()

class ReservePolicy:
    """Reduce usable equity by reserve buffer"""
    def __init__(self,reserve_buffer_pct:Optional[Decimal]):
        self.reserve_pct=reserve_buffer_pct
    
    def apply(self,usable_equity:Decimal)->PolicyResult:
        if self.reserve_pct is None or self.reserve_pct==0:
            return PolicyResult(ok=True,value=usable_equity)
        adj=usable_equity*(Decimal(1)-self.reserve_pct)
        return PolicyResult(ok=True,value=adj,metadata={"reserve_pct":self.reserve_pct,"original":usable_equity})

class FixedFractionPolicy:
    def __init__(self,fraction_pct:Decimal,precision:int=28):
        self.fraction_pct=fraction_pct
        self.precision=precision
    
    def apply(self,usable_equity:Decimal,price:Decimal)->PolicyResult:
        if usable_equity<=0:
            return PolicyResult(ok=False,reason="ALLOC_EQ_USABLE_NONPOSITIVE")
        if price<=0 or not DecimalMathKernel.is_finite(price):
            return PolicyResult(ok=False,reason="ALLOC_MARK_PRICE_INVALID")
        raw_notional=DecimalMathKernel.safe_mul(usable_equity,self.fraction_pct)
        raw_qty=DecimalMathKernel.safe_div(raw_notional,price)
        if raw_qty is None or not DecimalMathKernel.is_finite(raw_qty):
            return PolicyResult(ok=False,reason="ALLOC_DECIMAL_INVALID")
        return PolicyResult(ok=True,value=raw_qty,metadata={"raw_notional":raw_notional,"fraction":self.fraction_pct})

class ExposureCapPolicy:
    def __init__(self,max_symbol_pct:Decimal,usable_equity:Decimal,price:Decimal,cap_mode:str):
        self.max_symbol_pct=max_symbol_pct
        self.usable_equity=usable_equity
        self.price=price
        self.cap_mode=cap_mode
    
    def apply(self,raw_qty:Decimal)->PolicyResult:
        max_notional=DecimalMathKernel.safe_mul(self.usable_equity,self.max_symbol_pct)
        max_qty=DecimalMathKernel.safe_div(max_notional,self.price)
        if max_qty is None:
            return PolicyResult(ok=False,reason="ALLOC_DECIMAL_INVALID")
        
        if self.cap_mode=="BLOCK" and raw_qty>max_qty:
            return PolicyResult(ok=False,reason="ALLOC_CAP_BREACH_BLOCK_MODE",metadata={"requested":raw_qty,"max_allowed":max_qty})
        
        capped_qty=min(raw_qty,max_qty)
        return PolicyResult(ok=True,value=capped_qty,metadata={"cap_applied":capped_qty<raw_qty,"requested":raw_qty,"capped":capped_qty})

class QuantizationPolicy:
    def __init__(self,step_size:Decimal):
        self.step_size=step_size
    
    def apply(self,raw_qty:Decimal)->PolicyResult:
        if self.step_size<=0:
            return PolicyResult(ok=False,reason="ALLOC_STEP_SIZE_INVALID")
        quantized=DecimalMathKernel.floor_to_step(raw_qty,self.step_size)
        return PolicyResult(ok=True,value=quantized,metadata={"rounding":"floor","step_size":self.step_size,"pre_quant":raw_qty})

class MinMaxQtyPolicy:
    def __init__(self,min_qty:Optional[Decimal],max_qty:Optional[Decimal]):
        self.min_qty=min_qty
        self.max_qty=max_qty
    
    def apply(self,quantized_qty:Decimal)->PolicyResult:
        if self.min_qty and quantized_qty<self.min_qty:
            return PolicyResult(ok=False,reason="ALLOC_MIN_QTY_NOT_MET",metadata={"qty":quantized_qty,"min_required":self.min_qty})
        if self.max_qty and quantized_qty>self.max_qty:
            return PolicyResult(ok=False,reason="ALLOC_MAX_QTY_EXCEEDED",metadata={"qty":quantized_qty,"max_allowed":self.max_qty})
        return PolicyResult(ok=True,value=quantized_qty)

class MinTradeNotionalPolicy:
    def __init__(self,min_notional_global:Decimal,min_notional_symbol:Optional[Decimal],price:Decimal):
        self.min_notional=max(min_notional_global,min_notional_symbol or Decimal(0))
        self.price=price
    
    def apply(self,quantized_qty:Decimal)->PolicyResult:
        notional=DecimalMathKernel.safe_mul(quantized_qty,self.price)
        if notional is None or notional<self.min_notional:
            return PolicyResult(ok=False,reason="ALLOC_MIN_NOTIONAL_NOT_MET",metadata={"notional":notional,"min_required":self.min_notional})
        return PolicyResult(ok=True,value=quantized_qty,metadata={"notional":notional})
