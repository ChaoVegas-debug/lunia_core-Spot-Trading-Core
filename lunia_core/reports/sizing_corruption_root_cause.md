# SIZING CORRUPTION - ROOT CAUSE IDENTIFIED

**Date:** 2026-01-21 15:21  
**Forensic Tag:** `SEMANTIC_MODE_MISMATCH`  
**Status:** 🔴 **ROOT CAUSE CONFIRMED**

---

## SMOKING GUN

**SIZING_FORENSIC logs reveal:**

```
[SIZING_FORENSIC] side=SELL balance=530.383393 target_notional=503.86422335 
price=50352.78 computed_qty=0.010 current_position=0.187 step_size=0.001
```

**The Bug:**
- SELL computes: `qty = (balance * 0.95) / price = 530.38 * 0.95 / 50352.78 = 0.010`
- SELL should compute: `qty = position * 1.0 = 0.187`

**Classification:** SEMANTIC_MODE_MISMATCH

SELL is using **QUOTE NOTIONAL sizing** (like a BUY) instead of **BASE QUANTITY sizing** (position-based).

---

## CODE LOCATION

**File:** `app/simulation/genesis_harness_full.py`  
**Lines:** 294-297

```python
# CURRENT (WRONG - treats SELL like BUY):
price=current_price
target_notional=DecimalMathKernel.safe_mul(self.balance,Decimal("0.95"))
qty=DecimalMathKernel.safe_div(target_notional,price)
qty=DecimalMathKernel.floor_to_step(qty,self.constraints.qty_step_size)
```

**Problem:** Uses `self.balance` for ALL sides (BUY and SELL)

---

## THE FIX

```python
# CORRECT:
if proposal.side == "BUY":
    # BUY: Size by available cash (quote notional)
    target_notional = self.balance * Decimal("0.95")
    qty = target_notional / price
    
elif proposal.side == "SELL":
    # SELL: Size by current position (base quantity)
    qty = self.position_qty  # Full position
    
# Apply normalization
qty = DecimalMathKernel.floor_to_step(qty, self.constraints.qty_step_size)
```

---

## VALIDATION

**Before fix:**
- SELL #1: qty=0.010 (from $530 balance)
- SELL #2: qty=0.019 (from $1,033 balance)  
- SELL #3: qty=0.037...
- SELL #5: qty=0.141 → OVERSELL crash

**After fix (expected):**
- SELL #1: qty=0.187 (full position)
- No subsequent SELLs (position closed)
- No OVERSELL errors
- Clean survival

---

## FORENSIC TRACE COMPLETE

**Evidence trail:**
1. ✅ Strategy emits SELL intent
2. ✅ Harness sizes via balance/price = 0.010
3. ✅ Exchange fills 0.010
4. ✅ Accounting decrements position: 0.187 - 0.010 = 0.177
5. ✅ Next bar: SELL again, sizes via new balance
6. ✅ Eventually OVERSELL assert triggers (fail-fast working!)

**Root cause:** Lines 294-297 don't distinguish BUY from SELL.

---

**Next:** Apply surgical fix, re-run autopsy, verify GREEN.
