# Phase 6 Visual Annex Runbook — Operator Execution Guide

**Version**: 1.0  
**Date**: February 4, 2026  
**Duration**: ~10 minutes  
**Operator**: _______________________  
**Environment**: Production Baseline (localhost)

---

## Objective

Capture manual UI evidence to complete Phase 6 Visual Annex and achieve **FULLY CERTIFIED** status for the LUNIA/ALADDIN production baseline.

---

## Preconditions (VERIFY BEFORE STARTING)

### Backend Health

```bash
curl -s http://localhost:8080/health
# Expected: 200 OK (server responding)
```

### Frontend Availability

```bash
curl -s http://localhost:5173/ | head -5
# Expected: HTML content returned (Vite dev server)
```

**STOP**: If any precondition fails, fix the issue before proceeding.

---

## 10-Minute Execution Sequence

### T+0:00 — Setup (1 minute)

1. **Open Browser**: Chrome, Firefox, or Safari
2. **Navigate**: <http://localhost:5173/trader>
3. **Wait**: Page loads completely (2-3 seconds)
4. **Open DevTools**: Press `F12` or `Cmd+Option+I` (macOS)
5. **Position Windows**: Browser on left, DevTools on right
6. **Prepare Screenshot Tool**: macOS Screenshot (Cmd+Shift+4) ready

**Checkpoint**: Trader dashboard visible, DevTools Console + Network tabs accessible.

---

### T+1:00 — Full Dashboard Capture (30 seconds)

**Action**: Capture entire /trader page

**Screenshot**: `phase6_ui_trader_full_20260204_HHMM.png`

**PASS Criteria**:

- [ ] Page loads without error boundary
- [ ] Header visible with system mode indicator
- [ ] Widgets render (no blank sections)
- [ ] No React "white screen of death"

**Timestamp**: ________ (record actual capture time)

---

### T+1:30 — Console Clean Check (1 minute)

**Action**: Hard refresh and observe console

1. **Hard Refresh**: `Cmd+Shift+R` (macOS) or `Ctrl+Shift+R` (Windows/Linux)
2. **Wait**: 5 seconds for initial load
3. **Scroll Console**: Review all messages
4. **Capture Console**: Screenshot DevTools Console tab

**Screenshot**: `phase6_ui_console_clean_20260204_HHMM.png`

**PASS Criteria**:

- [ ] NO red runtime errors (React errors, `.map` failures, undefined exceptions)
- [ ] Warnings/info logs acceptable (CORS, deprecation notices OK)
- [ ] [POLLER] logs visible if debugging enabled

**Timestamp**: ________

---

### T+2:30 — Network Requests Proof (1 minute)

**Action**: Switch to Network tab and verify API calls

1. **DevTools**: Click **Network** tab
2. **Filter**: Type `localhost:8080` in filter box
3. **Observe**: API requests to backend
4. **Capture**: Screenshot showing request list with status codes

**Screenshot**: `phase6_ui_network_20260204_HHMM.png`

**PASS Criteria**:

- [ ] Requests to `http://localhost:8080/ops/*` visible
- [ ] Status codes: `200 OK` or `304 Not Modified`
- [ ] NO `500`, `502`, `503` errors
- [ ] NO `ERR_CONNECTION_REFUSED`

**Timestamp**: ________

---

### T+3:30 — Allocation Widgets State (1 minute)

**Action**: Scroll to allocation widgets section

1. **Locate**: ExchangeAllocationWidget
2. **Locate**: StrategyAllocationWidget
3. **Capture**: Both widgets in single screenshot

**Screenshot**: `phase6_ui_allocations_20260204_HHMM.png`

**PASS Criteria**:

- [ ] ExchangeAllocationWidget renders (empty state: "No allocations configured")
- [ ] StrategyAllocationWidget renders (empty state: "No allocations configured")
- [ ] NO red error boundary around widgets
- [ ] NO "allocations.map is not a function" crash

**Timestamp**: ________

---

### T+4:30 — Heartbeat Observation: T+0 (30 seconds)

**Action**: Locate Global AGE display

1. **Find**: Global AGE value (typically in header or status widget)
2. **Note**: Current AGE value: ______ seconds
3. **Capture**: Screenshot showing AGE clearly

**Screenshot**: `phase6_ui_age_t0_20260204_HHMM.png`

**Expected**: AGE < 10 seconds

**Timestamp**: ________

---

### T+5:00 — Heartbeat Observation: T+30 (30 seconds + 30s wait)

**Action**: Wait 30 seconds, observe AGE again

1. **Wait**: 30 seconds (use timer)
2. **Observe**: Global AGE value: ______ seconds
3. **Capture**: Screenshot

**Screenshot**: `phase6_ui_age_t30_20260204_HHMM.png`

**Expected**: AGE < 10 seconds, value has reset at least once

**Timestamp**: ________

---

### T+5:30 — Heartbeat Observation: T+60 (30 seconds + 30s wait)

**Action**: Wait additional 30 seconds (60s total)

1. **Wait**: 30 more seconds
2. **Observe**: Global AGE value: ______ seconds
3. **Capture**: Screenshot

**Screenshot**: `phase6_ui_age_t60_20260204_HHMM.png`

**Expected**: AGE < 10 seconds, at least 2 resets observed across 60s window

**Timestamp**: ________

---

### T+6:00 — Optional: T+120 Extended Observation (2 minutes)

**Action**: For full heartbeat certification, continue to T+120

1. **Wait**: 60 more seconds (120s total)
2. **Observe**: Global AGE value: ______ seconds
3. **Capture**: Screenshot

**Screenshot**: `phase6_ui_age_t120_20260204_HHMM.png`

**Expected**: AGE < 10 seconds sustained, multiple resets

**Timestamp**: ________

---

### T+8:00 — Governance via UI: STOP ALL (2 minutes)

**Objective**: Execute governance action through UI and prove state mutation.

#### Step 1: Pre-Governance State (30s)

**Action**: Note current system mode

1. **Find**: System mode chip/badge
2. **Verify**: Current mode (likely "MANUAL" or "ACTIVE")
3. **Capture**: Screenshot showing current mode

**Screenshot**: `phase6_ui_governance_before_20260204_HHMM.png`

**Current Mode**: ____________

---

#### Step 2: Execute STOP ALL (30s)

**Action**: Click STOP ALL button

1. **Locate**: "STOP ALL" or "Emergency Halt" button
2. **Click**: STOP ALL button
3. **Observe**: UI feedback (modal, confirmation, or immediate state change)
4. **Capture**: Airlock/confirmation screen (if present)
5. **Confirm**: Complete the governance action

**Screenshot**: `phase6_ui_stop_all_airlock_20260204_HHMM.png`

**Timestamp**: ________

---

#### Step 3: Post-Governance State (30s)

**Action**: Verify UI updates

1. **Observe**: Mode indicator changes
2. **Look for**: "STOP" badge (likely red/critical styling)
3. **Verify**: UI reflects immutability (controls disabled/grayed)
4. **Capture**: Screenshot showing updated state

**Screenshot**: `phase6_ui_mode_chip_stop_20260204_HHMM.png`

**New Mode**: ____________

**Timestamp**: ________

---

#### Step 4: Backend Verification (30s)

**Action**: Confirm backend state via curl

```bash
curl -s http://localhost:8080/ops/state | python3 -m json.tool | grep -E '"system_mode"|"global_stop"|"trading_on"'
```

**Expected Output**:

```json
"system_mode": "STOP",
"global_stop": true,
"trading_on": false
```

**Save output to**: `phase6_ui_governance_backend_proof_20260204_HHMM.txt`

---

## PASS/FAIL Rubric (Quick Reference)

| Item | PASS Criteria | FAIL Indicators |
| :--- | :--- | :--- |
| **Full Dashboard** | Page loads, widgets visible, no error boundary | White screen, React crash, blank page |
| **Console** | No red errors, warnings OK | `.map not a function`, TypeError, Uncaught errors |
| **Network** | 200/304 status codes to localhost:8080 | 500 errors, CONNECTION_REFUSED |
| **Allocations** | Widgets render (empty state visible) | Error boundaries, crash messages |
| **Heartbeat AGE** | AGE < 10s sustained, resets observed (60-120s) | AGE frozen, AGE > 10s sustained, N/A |
| **Governance UI** | Mode changes MANUAL→STOP, visual feedback | No UI update, mode stuck, controls still active |
| **Backend Proof** | system_mode=STOP, global_stop=true | State unchanged, curl fails |

**Overall Verdict**:

- **✅ PASS**: All items meet PASS criteria → Proceed to Evidence Report
- **❌ FAIL**: Any item has FAIL indicators → Remediation required

---

## File Naming Convention

**Format**: `phase6_ui_<component>_YYYYMMDD_HHMM.png`

**Example**: `phase6_ui_trader_full_20260204_1015.png`

**Directory**: Store all screenshots in `docs/phase6_evidence/` (create if needed)

---

## Troubleshooting

### Issue: Backend not responding

```bash
ps aux | grep flask_app
# If not running:
cd /Users/neomind/alladin/lunia_core-Spot-Trading-Core
export PORT=8080
python3 -m lunia_core.app.services.api.flask_app &
```

### Issue: Frontend not responding

```bash
cd /Users/neomind/alladin/lunia_core-Spot-Trading-Core/frontend
npm run dev
```

### Issue: Screenshots blurry or unclear

- Use native resolution (no browser zoom)
- Capture full window or specific regions clearly
- Ensure DevTools Console/Network tabs are fully visible

---

## Next Steps

After completing this runbook:

1. **Fill in** `phase6_visual_annex_report.md` with findings and paste screenshot filenames
2. **Attach screenshots** to `docs/phase6_evidence/` directory
3. **Update** `phase6_production_baseline_certification.md` with FULLY CERTIFIED status
4. **Commit** evidence to repository with governance timestamp

**Expected Outcome**: ✅ **PHASE 6 FULLY CERTIFIED — VISUAL ANNEX COMPLETE**
