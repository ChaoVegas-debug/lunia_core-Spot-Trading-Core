# AUTOPSY FINDINGS REPORT

**Date:** 2026-01-21  
**Forensic Tag:** `QTY_NOTIONAL_MISMATCH`  
**Status:** 🔴 **ROOT CAUSE IDENTIFIED**

---

## EXECUTIVE SUMMARY

The $10,000 → $1,033 (89.66% loss) equity death is caused by a **quantity mismatch bug** in the SELL operation. The system BUYS 0.187 BTC but SELLS only 0.010 BTC, then incorrectly zeros the entire position, destroying the remaining 0.177 BTC (~$8,900).

---

## FORENSIC EVIDENCE

### [FILL_APPLY_FORENSIC] Logs

**Transaction 1 - BUY (CORRECT):**
```
side=BUY
qty=0.187 BTC
price=$50,639.66
notional=$9,469.62
fee=$0.000187
cash_before=$10,000
cash_after=$530.38
pos_qty_after=0.187 BTC
equity_after=$10,000.00 ✅
delta_equity=$0.0006 (fee rounding)
```

**Transaction 2 - SELL (BUG EXPOSED):**
```
side=SELL
qty=0.010 BTC  ← SHOULD BE 0.187!
price=$50,352.78
notional=$503.53  ← ONLY SOLD $500 WORTH!
fee=$0.000010
cash_before=$530.38
cash_after=$1,033.91
pos_qty_before=0.187 BTC
pos_qty_after=0  ← WRONGLY ZEROED!
equity_before=$9,946.35
equity_after=$1,033.91
delta_equity=-$8,912.44  ← 90% LOSS HERE!
```

---

## ROOT CAUSE ANALYSIS

### The Bug Location

**File:** `app/simulation/genesis_harness_full.py`  
**Lines:** 404-409

```python
elif proposal.side=="SELL":
    proceeds=DecimalMathKernel.safe_mul(fill.filled_qty,fill.fill_price) or Decimal("0")
    self.balance+=(proceeds-fill.fee)
    self.position_qty=Decimal("0")  ← BUG: Unconditionally zeros position!
    self.position_entry_price=Decimal("0")
    self.strategy.update_position(None)
```

**The Problem:**
1. SELL order was for 0.010 BTC (not 0.187 BTC - sizing bug upstream)
2. Fill qty = 0.010 BTC  
3. Code sets `position_qty=Decimal("0")` WITHOUT checking if full position was sold
4. Remaining 0.177 BTC ($8,900) **destroyed** from accounting

---

## UPSTREAM SIZING BUG

The SELL was sized at 0.010 BTC instead of 0.187 BTC. Need to trace:

1. **AllocationEngine** - What did it compute?
2. **Preflight** - Did it normalize incorrectly?
3. **Strategy** - Did it emit wrong qty?

**Hypothesis:** SELL may have been sized as QUOTE_NOTIONAL ($500) misinterpreted as BASE_QTY (0.010 BTC).

---

## THE FIX (Phase 0 Scope)

### Immediate Fix (Accounting Assert)
```python
elif proposal.side=="SELL":
    proceeds=DecimalMathKernel.safe_mul(fill.filled_qty,fill.fill_price) or Decimal("0")
    self.balance+=(proceeds-fill.fee)
    
    # FIX: Decrement position by filled qty, don't zero
    self.position_qty -= fill.filled_qty
    
    # ASSERT: Position shouldn't go negative
    if self.position_qty < Decimal("0"):
        raise RuntimeError(f"OVERSELL: Sold {fill.filled_qty} but only had {self.position_qty + fill.filled_qty}")
    
    # Only zero entry if fully closed
    if self.position_qty <= Decimal("0.0001"):
        self.position_qty = Decimal("0")
        self.position_entry_price = Decimal("0")
        self.strategy.update_position(None)
```

### Full Fix (Find Sizing Bug)
Need to trace why SELL qty = 0.010 instead of 0.187.

Add `[SIZING_FORENSIC]` logs to AllocationEngine.

---

## CLASSIFICATION

**Primary Tag:** `QTY_NOTIONAL_MISMATCH`  
**Secondary Tags:** `OVERSELL_POSITION` (accounting violated)  
**Severity:** CRITICAL  
**Unexplained Loss:** $8,966.09

---

## REPLAY PACK

**Location:** `replay_packs/autopsy_10k_to_1k_seed42.json`  
**Deterministic:** YES (seed=42 reproduces 100%)  
**Logs:** `replay_packs/autopsy_forensic.log`

---

## NEXT STEPS (PHASE 0)

1. ✅ **Root cause identified** - SELL qty mismatch + unconditional position zeroing
2. **Apply immediate fix** - Decrement position instead of zeroing
3. **Add sizing forensic logs** - Trace upstream qty computation
4. **Create conservation law test** - Verify fix prevents this class of bug
5. **Re-run autopsy** - Should pass after fix

---

**End of Autopsy Report**
