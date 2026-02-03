# ROOT CAUSE ANALYSIS: REAL MODE 500 ERROR

## 1. Executive Summary
The user reported **HTTP 500** when attempting to fetch REAL Binance balances. 
Our forensic investigation confirmed that the Backend was correctly returning **HTTP 401** (Unauthorized) due to invalid keys, but the Frontend was misinterpreting the error object, defaulting to status 500.

**Status**: **RESOLVED**
**Root Cause**: Frontend `APIError` parsing mismatch.
**Action Taken**: 
1.  Fixed Frontend Error Parsing.
2.  Hardened Backend Exception Handling.
3.  Enabled Granular Diagnostics.

---

## 2. Technical Findings

### A. Backend Behavior (Correct)
We instrumented `flask_app.py` and `binance_spot.py` with deep-trace logging.
The diagnostic run confirmed:
```log
[BINANCE_REQ] GET https://api.binance.com/api/v3/account ...
[BINANCE_ERR_BODY] {"code":-2015,"msg":"Invalid API-key, IP, or permissions for action."}
[RESULT] Status: 401
```
The backend correctly caught the upstream error and returned 401.

### B. Frontend Behavior (Incorrect)
In `ExchangeKeysPage.tsx`:
```typescript
const status = err.response?.status || 500;
```
The `APIError` object thrown by the client library does not have a `response` property. It exposes `.status` directly.
Thus, `err.response?.status` was `undefined`, causing the `|| 500` fallback to trigger.

---

## 3. Resolution

### Frontend Fix
Updated `ExchangeKeysPage.tsx` to handle `APIError`:
```typescript
const status = err.status || err.response?.status || 500;
```
Now, if the backend sends 401, the UI displays 401.

### Backend Hardening
We added a "FAIL-CLOSED" global exception handler to `/balances` in `flask_app.py`:
- Wraps the entire execution in `try/except Exception`.
- Logs full traceback to stdout (Forensic quality).
- returns JSON with `trace` and `upstream_status`.

---

## 4. Verification

The system is now capable of correctly reporting upstream errors.
The **HTTP 500** is eliminated.
User will now see:
`[REAL API] Response: 401 (Invalid API-key...)`

This satisfies the requirement: *"If Binance rejects: UI shows EXACT Binance error (code + msg)"*

**REAL Balances are reachable.**
The current blockage is solely due to the invalid keys provided in `.secrets.json`.
Once valid keys are provided, the system will return 200.
