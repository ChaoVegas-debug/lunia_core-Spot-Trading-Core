"""Simple Risk Engine with PRE-TRADE gating and correct DD math"""
from decimal import Decimal
from pydantic import BaseModel

class RiskConfig(BaseModel):
    max_drawdown_threshold:Decimal=Decimal("0.20")
    enable_drawdown_check:bool=True

class RiskContext(BaseModel):
    current_equity:Decimal
    peak_equity:Decimal
    position_qty:Decimal
    drawdown_pct:Decimal
    
    class Config:
        arbitrary_types_allowed=True

class RiskDecision(BaseModel):
    decision:str  # ALLOW, BLOCK, HALT
    reason:str=""
    severity:str="NORMAL"  # NORMAL, WARNING, CRITICAL

def compute_drawdown(peak_equity:Decimal,current_equity:Decimal)->Decimal:
    """
    Compute drawdown with fail-fast invariants
    
    DD = (peak - current) / peak
    """
    if peak_equity<=0:
        raise ValueError(f"INVALID_PEAK_EQUITY: {peak_equity}")
    
    dd=(peak_equity-current_equity)/peak_equity
    
    # Sanity check
    if dd<0 or dd>Decimal("1"):
        raise ValueError(f"DD_OUT_OF_RANGE: dd={dd}, peak={peak_equity}, current={current_equity}")
    
    return dd

class RiskEngine:
    """Risk Engine with PRE-TRADE gating"""
    
    def __init__(self,config:RiskConfig):
        self.config=config
    
    def evaluate_intent(self,symbol:str,side:str,qty:Decimal,price:Decimal,context:RiskContext)->RiskDecision:
        """
        Evaluate if intent should be allowed (PRE-TRADE)
        
        Blocks if CURRENT drawdown already exceeds threshold
        (prevents further damage)
        """
        # Recompute DD with correct math
        dd=compute_drawdown(context.peak_equity,context.current_equity)
        
        # Check CURRENT state first
        if self.config.enable_drawdown_check:
            if dd>=self.config.max_drawdown_threshold:
                return RiskDecision(
                    decision="BLOCK",
                    reason=f"MAX_DRAWDOWN_EXCEEDED: {dd:.2%} >= {self.config.max_drawdown_threshold:.2%}",
                    severity="CRITICAL"
                )
        
        # TODO: Add projected DD check (worst-case after this trade)
        # For MVP: blocking at current threshold is sufficient
        
        return RiskDecision(decision="ALLOW",reason="",severity="NORMAL")

# Unit sanity check
if __name__=="__main__":
    # Test 1: 25% DD
    dd1=compute_drawdown(Decimal("10000"),Decimal("7500"))
    assert abs(dd1-Decimal("0.25"))<Decimal("0.001"),f"Expected 0.25, got {dd1}"
    
    # Test 2: 86.57% DD  
    dd2=compute_drawdown(Decimal("10000"),Decimal("1343"))
    expected=Decimal("0.8657")
    assert abs(dd2-expected)<Decimal("0.001"),f"Expected {expected}, got {dd2}"
    
    print("✅ DD math sanity checks passed")
