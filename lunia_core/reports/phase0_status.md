# PHASE 0 STATUS REPORT

**Date:** 2026-01-21  
**Mode:** EXCLUSIVE - Money Physics Only  
**Token Budget:** ~70k remaining

---

## ✅ COMPLETED TASKS

### A) PRIMARY AUTOPSY ✅
- **Test Created:** `tests/forensic/test_primary_autopsy_10k_to_1k.py`
- **Bug Reproduced:** Deterministically (seed=42)
- **Forensic Tag:** `QTY_NOTIONAL_MISMATCH`
- **Replay Pack:** `replay_packs/autopsy_10k_to_1k_seed42.json`
- **Forensic Logs:** `replay_packs/autopsy_forensic.log`
- **Root Cause Report:** `reports/autopsy_findings.md`

**Finding:** SELL qty=0.010 instead of 0.187, position unconditionally zeroed, destroying $8,900.

### B) FORENSIC INFRASTRUCTURE ✅
- **Classifier:** `forensic/classifier.py` - Tags accounting failures
- **Logging:** `forensic/logging.py` - Structured observation
- **[FILL_APPLY_FORENSIC]:** Added to harness (lines 399-402, 421-425)

### C) ACCOUNTING FIX (PARTIAL) ✅
- **File:** `app/simulation/genesis_harness_full.py`  
- **Lines:** 404-423
- **Change:** SELL now decrements position instead of zeroing
- **Assert:** OVERSELL detection (fail-fast)

**Result:** Fix prevents catastrophic $8,900 loss BUT exposes deeper bug...

---

## 🔴 NEW DISCOVERY

**After applying the accounting fix, the system now CRASHES with:**

```
RuntimeError: [ACCOUNTING_FAILURE] OVERSELL: 
Attempted to sell 0.141 but only held 0.049.
Forensic tag: OVERSELL_POSITION
```

**Analysis:**
- Multiple SELL attempts occurring
- SELL quantities don't match actual position
- This is UPSTREAM sizing bug, not accounting bug

**This is GOOD** - PHASE 0 fail-fast working correctly!

---

## 🎯 ROOT CAUSE UPDATED

**Two-Layer Bug:**

1. **Layer 1 (FIXED):** Unconditional position zeroing  
   - ❌ Before: `position_qty = Decimal("0")` 
   - ✅ After: `position_qty -= fill.filled_qty`

2. **Layer 2 (EXPOSED):** Sizing mismatch  
   - BUY: 0.187 BTC ✅
   - SELL #1: 0.010 BTC (should be 0.187)
   - SELL #2: 0.141 BTC (but only 0.177 left!)
   - **Upstream bug:** AllocationEngine or Strategy emitting wrong SELL quantities

---

## 📊 ACCEPTANCE CRITERIA STATUS

**A) PRIMARY AUTOPSY:** ✅ COMPLETE  
- $10k→$1k reproduced deterministically
- Forensic tag assigned
- Replay pack created

**B) CONSERVATION LAWS:** 🟡 IN PROGRESS  
- Need to trace sizing bug
- Need to add SIZING_FORENSIC logs

**C) EXCHANGE SEMANTICS:** ⏳ PENDING  
- Need to verify MARKET vs LIMIT semantics
- Need to check qty normalization

**D) DETERMINISM:** ✅ PROVEN  
- Same seed → same failure

**E) FORENSIC LOGGING:** ✅ ACTIVE  
- [FILL_APPLY_FORENSIC] working
- Need [SIZING_FORENSIC]

**F) NO ARCHITECTURE VIOLATIONS:** ✅ CONFIRMED  
- No risk gates added
- No emergency logic added
- Pure accounting only

---

## 📋 NEXT STEPS

### Priority 1: Trace Sizing Bug
Add `[SIZING_FORENSIC]` logs to:
1. AllocationEngine (where qty is computed)
2. Strategy (where SELL intent is created)
3. Preflight (where normalization happens)

### Priority 2: Conservation Law Tests
Create `tests/forensic/test_conservation_laws.py`:
- Roundtrip at constant price
- No overspend/oversell
- Unit semantics integrity

### Priority 3: Fix Sizing Bug
Once traced, fix the upstream qty mismatch.

### Priority 4: Re-run Autopsy
Should pass after full fix.

---

## 🔬 FORENSIC EVIDENCE SUMMARY

**Files Created:**
1. `/forensic/classifier.py`
2. `/forensic/logging.py`
3. `/tests/forensic/test_primary_autopsy_10k_to_1k.py`
4. `/replay_packs/autopsy_10k_to_1k_seed42.json`
5. `/replay_packs/autopsy_forensic.log`
6. `/reports/autopsy_findings.md`
7. `/reports/phase0_status.md` (this file)

**Code Modified:**
1. `app/simulation/genesis_harness_full.py` - Fixed SELL accounting, added forensic logs

---

**PHASE 0: 60% COMPLETE**  
**Estimated tokens to completion:** ~30-40k

**Next action:** Add SIZING_FORENSIC logs and trace the qty mismatch.
