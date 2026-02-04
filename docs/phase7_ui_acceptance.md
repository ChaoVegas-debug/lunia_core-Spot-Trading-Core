# Phase 7.5 UI Acceptance — Manual Verification Checklist

**Date**: February 4, 2026  
**Branch**: `feat/phase7-synthetic-advisor`  
**Commit**: `5bf12e0`

---

## Acceptance Criteria (HARD GATE)

**All criteria must PASS before Phase 7.5 is considered complete.**

---

### 1. Frontend Loads Without Errors

**Test**: Open `/trader` dashboard

**Expected**:

- ✅ Page loads successfully
- ✅ Zero red console errors
- ✅ No white screen of death
- ✅ No `.map is not a function` errors

**Status**: ⚠️ **PENDING** (requires manual verification)

---

### 2. AdvisorWidget Renders Correctly

**Test**: Add `<AdvisorWidget />` to trader dashboard

**Expected**:

- ✅ Widget displays with `🧠 AI ADVISOR` header
- ✅ Empty state shows "SHADOW MODE ACTIVE" when no AI data
- ✅ AI analysis displays when available (after migration + mock data)
- ✅ Risk flags render as chips if present
- ✅ Confidence bar displays correctly
- ✅ Provenance chips show model/latency/cost
- ✅ Feedback buttons (👍/👎) are clickable
- ✅ "SECONDARY — CORE DISAGREES" badge shows when `conflicts_with_core = true`

**Status**: ⚠️ **PENDING**

---

### 3. JournalSignalsWidget Renders Signal List

**Test**: Add `<JournalSignalsWidget />` to dashboard

**Expected**:

- ✅ Widget displays with `📝 EXECUTION JOURNAL` header
- ✅ Signals list populated (after migration + signal persistence)
- ✅ Empty state shows "No signals in execution journal" when empty
- ✅ Each signal card shows: symbol, signal_type, confidence bar
- ✅ 🧠 Brain icon visible on each signal
- ✅ Brain icon clickable (opens modal)
- ✅ Conflict badge (⚠️ AI CONFLICT) shows when AI disagrees
- ✅ Core vs AI confidence comparison displays when AI present

**Status**: ⚠️ **PENDING**

---

### 4. ExecutionJournalModal Opens Reliably

**Test**: Click🧠 brain icon on any signal

**Expected**:

- ✅ Modal opens instantly (no lag)
- ✅ Dual-pane layout renders (LEFT: Core, RIGHT: AI)
- ✅ LEFT pane shows deterministic reasoning
- ✅ LEFT pane shows risk filters (JSON formatted)
- ✅ LEFT pane shows market context (JSON formatted)
- ✅ RIGHT pane shows AI summary (or empty state if no AI)
- ✅ RIGHT pane shows confidence bar if AI present
- ✅ RIGHT pane shows risk flags if present
- ✅ Conflict warning banner shows when `conflicts_with_core = true`
- ✅ Close button works
- ✅ Modal closes on ESC key (if implemented)

**Status**: ⚠️ **PENDING**

---

### 5. Feedback Buttons Return 200 OK

**Test**: Click 👍 Helpful or 👎 Hallucination

**Expected**:

- ✅ POST request to `/api/journal/feedback` returns 200
- ✅ Feedback persisted to `ai_analysis` table
- ✅ Button becomes disabled after submission
- ✅ TraceDrawer `AI_FEEDBACK` event emitted
- ✅ Comment box appears when clicking 👎
- ✅ Comment persists correctly

**Status**: ⚠️ **PENDING**

---

### 6. No Regression of .map Errors

**Test**: Load dashboard with all widgets

**Expected**:

- ✅ No `.map is not a function` errors in console
- ✅ All `Array.isArray()` guards working
- ✅ Null/undefined fallbacks prevent crashes
- ✅ Empty arrays default to `[]`
- ✅ Empty objects default to `{}`

**Status**: ⚠️ **PENDING**

---

### 7. UI Survives Backend Errors

**Test**: Simulate backend failures

**Scenarios**:

1. Backend returns `null`
   - ✅ Widget shows empty state, NOT error
2. Backend returns `{ error: "..." }`
   - ✅ FailClosedPanel displays error gracefully
3. Backend returns incomplete JSON
   - ✅ Widget shows empty state, NOT crash
4. Backend times out
   - ✅ Stale indicator appears
   - ✅ Last good data shown (if available)
5. Backend unavailable (503)
   - ✅ FailClosedPanel shows "Service unavailable"

**Status**: ⚠️ **PENDING**

---

## Prerequisites for Testing

### Backend Setup

1. **Apply DB Migration**:

   ```bash
   cd lunia_core
   python3 -m alembic upgrade head
   ```

   **Verify**:

   ```bash
   sqlite3 data/lunia.db ".tables" | grep signal_events
   ```

   Should output: `signal_events`, `ai_analysis`, `ai_inference_logs`

2. **Seed Test Data** (optional):

   ```python
   # Run test_phase7_simple.py to generate mock signal + AI analysis
   python3 -m lunia_core.tests.test_phase7_simple
   ```

3. **Start Backend**:

   ```bash
   cd lunia_core
   python3 -m app.services.api.flask_app
   ```

### Frontend Setup

1. **Add Widgets to Dashboard**:
   Edit `frontend/src/pages/TraderDashboard.tsx` or create test page:

   ```tsx
   import { AdvisorWidget } from '../components/widgets/AdvisorWidget';
   import { JournalSignalsWidget } from '../components/widgets/JournalSignalsWidget';
   
   // Add to layout:
   <AdvisorWidget />
   <JournalSignalsWidget />
   ```

2. **Start Frontend**:

   ```bash
   cd frontend
   npm run dev
   ```

3. **Open Browser**:

   ```
   http://localhost:5173/trader
   ```

---

## Known Limitations (Not Blockers)

### Real LLM Providers Not Implemented

**Reason**: Cost control, API key management complexity

**Impact**: Only MockProvider available (returns synthetic data)

**Future Work**:

- Implement `OpenAIProvider`
- Implement `AnthropicProvider`
- Add secure API key storage (Vault)
- Add rate limit handling

### SignalsWidget Not Modified

**Reason**: Existing SignalsWidget uses `/api/signals/active` API with different schema

**Solution**: Created separate `JournalSignalsWidget` for Execution Journal display

**Future Work**: Migrate existing signals API to use Execution Journal persistence

### No Automatic Signal Persistence

**Reason**: EventBus hook not yet wired to strategy signal emission

**Impact**: Signals must be manually created via test scripts

**Future Work**: Add `SIGNAL_GENERATED` → `persist_signal_event()` hook in strategy runner

---

## Verification Commands

### 1. Check Backend API

```bash
# Test signals endpoint (should return empty array initially)
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/api/journal/signals

# Test signal detail (after creating test signal)
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/api/journal/signal/<signal_id>

# Test feedback submission
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"analysis_id": "<id>", "feedback": "thumbs_up"}' \
  http://localhost:8080/api/journal/feedback
```

### 2. Check Frontend Console

**No Errors**:

- Warnings about missing data are OK
- Red errors are NOT OK

**Expected Warnings** (acceptable):

```
[AdvisorWidget] No AI analysis available (Shadow Mode)
[JournalSignalsWidget] No signals found
```

**Unacceptable Errors**:

```
TypeError: Cannot read property 'map' of undefined
ReferenceError: ... is not defined
```

---

## Sign-Off

Once all criteria marked ✅ **PASS**, Phase 7.5 is CERTIFIED.

**Operator Signature**: _______________  
**Date**: _______________  
**Notes**: _______________

---

**Phase 7.5 UI Legitimacy Layer COMPLETE when all PASS.**
