"""Execution Math Conservation Tests - BLOCKING STEP

These tests MUST pass before implementing transition gate.
They prove SELL execution doesn't destroy principal.
"""
import pytest
from decimal import Decimal
from app.services.allocation.policies import DecimalMathKernel

class TestPortfolio:
    """Minimal portfolio for testing execution math"""
    
    def __init__(self,initial_cash:Decimal):
        DecimalMathKernel.ensure_context(28)
        self.cash=initial_cash
        self.position_qty=Decimal("0")
        self.position_entry_price=Decimal("0")
        self.fees_paid=Decimal("0")
    
    def apply_buy_fill(self,qty:Decimal,fill_price:Decimal,fee:Decimal):
        """BUY: pay cash for position"""
        cost=qty*fill_price
        self.cash-=(cost+fee)
        self.fees_paid+=fee
        
        if self.position_qty>0:
            total_cost=(self.position_qty*self.position_entry_price)+cost
            self.position_qty+=qty
            self.position_entry_price=total_cost/self.position_qty
        else:
            self.position_qty=qty
            self.position_entry_price=fill_price
    
    def apply_sell_fill(self,qty:Decimal,fill_price:Decimal,fee:Decimal):
        """SELL: receive cash from position (CRITICAL: must not destroy principal)"""
        proceeds=qty*fill_price
        self.cash+=(proceeds-fee)
        self.fees_paid+=fee
        self.position_qty-=qty
        
        if self.position_qty<=Decimal("0.0001"):
            self.position_qty=Decimal("0")
            self.position_entry_price=Decimal("0")
    
    def equity(self,current_price:Decimal)->Decimal:
        """Total equity = cash + position_value"""
        position_value=self.position_qty*current_price
        return self.cash+position_value

def test_roundtrip_no_price_move_conservation():
    """BUY then SELL at same price should only lose fees"""
    p=TestPortfolio(Decimal("10000"))
    
    price=Decimal("50000")
    qty=Decimal("0.19")  # 9500 notional
    fee_rate=Decimal("0.001")
    
    # BUY
    buy_fee=qty*price*fee_rate  # 9.5
    p.apply_buy_fill(qty,price,buy_fee)
    
    equity_after_buy=p.equity(price)
    print(f"After BUY: cash={p.cash}, qty={p.position_qty}, equity={equity_after_buy}")
    
    # SELL at same price
    sell_fee=qty*price*fee_rate  # 9.5
    p.apply_sell_fill(qty,price,sell_fee)
    
    equity_after_sell=p.equity(price)
    total_fees=buy_fee+sell_fee  # 19
    
    expected_final=Decimal("10000")-total_fees
    
    print(f"After SELL: cash={p.cash}, qty={p.position_qty}, equity={equity_after_sell}")
    print(f"Expected: {expected_final}, Actual: {equity_after_sell}, Diff: {abs(equity_after_sell-expected_final)}")
    
    assert abs(p.cash-expected_final)<Decimal("0.01"),f"Cash conservation failed: {p.cash} vs {expected_final}"
    assert p.position_qty==Decimal("0")
    assert abs(equity_after_sell-expected_final)<Decimal("0.01")

def test_small_adverse_move_conservation():
    """BUY then SELL at -2% should show proportional loss"""
    p=TestPortfolio(Decimal("10000"))
    
    buy_price=Decimal("50000")
    sell_price=Decimal("49000")  # -2%
    qty=Decimal("0.19")
    fee_rate=Decimal("0.001")
    
    # BUY
    buy_cost=qty*buy_price  # 9500
    buy_fee=buy_cost*fee_rate  # 9.5
    p.apply_buy_fill(qty,buy_price,buy_fee)
    
    # SELL at lower price
    sell_proceeds=qty*sell_price  # 9310
    sell_fee=sell_proceeds*fee_rate  # 9.31
    p.apply_sell_fill(qty,sell_price,sell_fee)
    
    # Expected: started with 10000, paid 9509.5 for position, got back 9300.69
    # Loss = 9509.5 - 9300.69 = 208.81
    # Final cash = 490.5 (left after buy) + 9300.69 (from sell) = 9791.19
    
    expected_loss=buy_cost+buy_fee-(sell_proceeds-sell_fee)
    expected_final=Decimal("10000")-expected_loss
    
    print(f"After -2% SELL: cash={p.cash}, expected={expected_final}, loss={expected_loss}")
    
    assert abs(p.cash-expected_final)<Decimal("1"),f"Conservation failed on -2% move: {p.cash} vs {expected_final}"
    assert p.cash>Decimal("9700"),f"Loss too large for -2% move: cash={p.cash}"
    assert p.cash<Decimal("10000"),f"Should have some loss"

def test_equity_includes_position_value():
    """After BUY, equity should include full position value, not just PnL"""
    p=TestPortfolio(Decimal("10000"))
    
    price=Decimal("50000")
    qty=Decimal("0.19")
    fee=qty*price*Decimal("0.001")
    
    p.apply_buy_fill(qty,price,fee)
    equity=p.equity(price)
    
    # Cash dropped by ~9509.5, but position worth 9500
    # Equity should be ~9990.5 (only lost fee)
    
    assert equity>Decimal("9980"),f"Equity too low: {equity} (should be ~9990)"
    assert equity<Decimal("10000"),f"Equity should have small fee loss"
    print(f"✅ Equity after BUY: {equity} (includes position value)")

if __name__=="__main__":
    pytest.main([__file__,"-v","-s"])
