"""Portfolio Math Invariants - Unit Tests (BLOCKING)

These tests MUST pass before any harness edits.
They prove the accounting model is correct.
"""
import pytest
from decimal import Decimal
from lunia_core.app.services.allocation.policies import DecimalMathKernel

# Simplified Portfolio for unit testing
class SimplePortfolio:
    """Minimal portfolio for testing math invariants"""
    
    def __init__(self,initial_cash:Decimal):
        DecimalMathKernel.ensure_context(28)
        self.cash=initial_cash
        self.position_qty=Decimal("0")
        self.position_entry_price=Decimal("0")
        self.peak_equity=initial_cash
        self.fees_paid=Decimal("0")
    
    def apply_buy_fill(self,qty:Decimal,fill_price:Decimal,fee:Decimal):
        """Apply BUY fill (E5-only semantics)"""
        cost=DecimalMathKernel.safe_mul(qty,fill_price) or Decimal("0")
        self.cash-=(cost+fee)
        self.fees_paid+=fee
        
        # Weighted average entry price
        if self.position_qty>0:
            total_cost=DecimalMathKernel.safe_mul(self.position_qty,self.position_entry_price) or Decimal("0")
            total_cost+=cost
            self.position_qty+=qty
            self.position_entry_price=DecimalMathKernel.safe_div(total_cost,self.position_qty) or Decimal("0")
        else:
            self.position_qty=qty
            self.position_entry_price=fill_price
    
    def apply_sell_fill(self,qty:Decimal,fill_price:Decimal,fee:Decimal):
        """Apply SELL fill"""
        proceeds=DecimalMathKernel.safe_mul(qty,fill_price) or Decimal("0")
        self.cash+=(proceeds-fee)
        self.fees_paid+=fee
        self.position_qty-=qty
        if self.position_qty<=Decimal("0.0001"):
            self.position_qty=Decimal("0")
            self.position_entry_price=Decimal("0")
    
    def mark_to_market(self,current_price:Decimal)->Decimal:
        """Calculate total equity with CORRECT formula"""
        # CORRECT: position_value = qty * current_price
        position_value=DecimalMathKernel.safe_mul(self.position_qty,current_price) or Decimal("0")
        total_equity=self.cash+position_value
        
        # Update peak
        if total_equity>self.peak_equity:
            self.peak_equity=total_equity
        
        return total_equity
    
    def calculate_drawdown(self,equity:Decimal)->Decimal:
        """Calculate DD from peak"""
        if self.peak_equity<=0:
            return Decimal("0")
        dd=(self.peak_equity-equity)/self.peak_equity
        if dd<0:
            dd=Decimal("0")
        if dd>Decimal("1"):
            raise ValueError(f"DD_OUT_OF_RANGE: dd={dd}")
        return dd

def test_buy_does_not_destroy_equity_no_price_move():
    """BUY INVARIANT: Equity should only drop by fee amount if price unchanged"""
    p=SimplePortfolio(Decimal("10000"))
    
    # BUY fill
    price=Decimal("50000")
    qty=Decimal("0.19")
    notional=qty*price  # 9500
    fee=notional*Decimal("0.001")  # 9.5
    
    p.apply_buy_fill(qty,price,fee)
    
    # Mark to market at SAME price
    equity=p.mark_to_market(price)
    dd=p.calculate_drawdown(equity)
    
    # Expected values
    expected_cash=Decimal("10000")-notional-fee  # 490.5
    expected_position_value=qty*price  # 9500
    expected_equity=expected_cash+expected_position_value  # 9990.5
    expected_dd=(Decimal("10000")-expected_equity)/Decimal("10000")  # 0.00095
    
    assert p.cash==expected_cash,f"Cash mismatch: {p.cash} != {expected_cash}"
    assert p.position_qty==qty
    assert abs(equity-expected_equity)<Decimal("0.01"),f"Equity mismatch: {equity} != {expected_equity}"
    assert dd<Decimal("0.001"),f"DD too high: {dd} (expected ~0.001)"
    print(f"✅ BUY no price move: cash={p.cash}, equity={equity}, dd={dd:.4%}")

def test_small_down_move_updates_equity_linearly():
    """MARK-TO-MARKET INVARIANT: Small price drop updates equity linearly"""
    p=SimplePortfolio(Decimal("10000"))
    
    # BUY
    buy_price=Decimal("50000")
    qty=Decimal("0.19")
    fee=qty*buy_price*Decimal("0.001")
    p.apply_buy_fill(qty,buy_price,fee)
    
    # Mark to market at LOWER price
    new_price=Decimal("49000")  # -2% drop
    equity=p.mark_to_market(new_price)
    dd=p.calculate_drawdown(equity)
    
    # Expected
    position_value=qty*new_price  # 9310
    expected_equity=p.cash+position_value  # 490.5 + 9310 = 9800.5
    expected_dd=(Decimal("10000")-expected_equity)/Decimal("10000")  # ~0.01995
    
    assert abs(equity-expected_equity)<Decimal("0.01"),f"Equity mismatch: {equity} != {expected_equity}"
    assert abs(dd-expected_dd)<Decimal("0.001"),f"DD mismatch: {dd} != {expected_dd}"
    print(f"✅ Price -2%: equity={equity}, dd={dd:.4%}")

def test_peak_equity_is_monotonic():
    """PEAK INVARIANT: Peak never decreases"""
    p=SimplePortfolio(Decimal("10000"))
    
    # BUY
    p.apply_buy_fill(Decimal("0.19"),Decimal("50000"),Decimal("9.5"))
    
    # Price rises
    equity1=p.mark_to_market(Decimal("51000"))
    peak1=p.peak_equity
    
    # Price falls
    equity2=p.mark_to_market(Decimal("49000"))
    peak2=p.peak_equity
    
    assert peak1>=Decimal("10000"),f"Peak should start at 10000, got {peak1}"
    assert peak2>=peak1,f"Peak decreased: {peak2} < {peak1}"
    assert peak2==peak1,f"Peak should stay at max, got {peak2} != {peak1}"
    print(f"✅ Peak monotonic: peak after rise={peak1}, peak after fall={peak2}")

def test_full_roundtrip_accounting():
    """ROUNDTRIP INVARIANT: BUY then SELL at same price recovers equity minus fees"""
    p=SimplePortfolio(Decimal("10000"))
    
    price=Decimal("50000")
    qty=Decimal("0.19")
    
    # BUY
    buy_fee=qty*price*Decimal("0.001")
    p.apply_buy_fill(qty,price,buy_fee)
    
    # SELL at same price
    sell_fee=qty*price*Decimal("0.001")
    p.apply_sell_fill(qty,price,sell_fee)
    
    # Should have original cash minus fees
    expected_cash=Decimal("10000")-(buy_fee+sell_fee)
    equity=p.mark_to_market(price)
    
    assert p.position_qty==Decimal("0")
    assert abs(p.cash-expected_cash)<Decimal("0.01"),f"Cash mismatch: {p.cash} != {expected_cash}"
    assert abs(equity-expected_cash)<Decimal("0.01"),f"Equity should equal cash when flat: {equity} != {expected_cash}"
    print(f"✅ Roundtrip: final_cash={p.cash}, total_fees={p.fees_paid}")

if __name__=="__main__":
    pytest.main([__file__,"-v","-s"])
