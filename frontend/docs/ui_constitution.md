# ALADDIN UI CONSTITUTION

**Version**: 1.0  
**Date**: 2026-01-29  
**Status**: LOCKED (changes require constitutional amendment process)

**Purpose**: This document establishes the **immutable laws and standards** governing the ALADDIN Institutional Terminal frontend. These laws prevent quality erosion, ensure fail-closed behavior, and maintain court-defensibility.

---

## THE 15 LAWS

### LAW 0: Three Eyes Principle (Role Segregation)

**Mandate**: Every role (TRADER, RISK_OFFICER, COMPLIANCE) sees ONLY controls permitted by their role.

**Implementation**:

- Forbidden controls MUST be **removed from DOM** (not just hidden via CSS)
- Role context MUST be verified at component mount
- Any role escalation attempt MUST trigger evidence recording (`UNAUTHORIZED_ACCESS_ATTEMPT`)

**Example**:

```tsx
// ❌ FORBIDDEN
<button disabled={role !== 'ADMIN'}>Delete All</button>

// ✅ COMPLIANT
{role === 'ADMIN' && <button>Delete All</button>}
```

---

### LAW 1: Chinese Wall (Workspace Isolation)

**Mandate**: Role workspaces MUST NOT share state or context without explicit evidence.

**Implementation**:

- Workspace transitions MUST route through `Context Switch Evidence` recording
- No shared localStorage keys across workspaces (prefix with `workspace:${role}:`)
- Cross-workspace data access MUST be logged as `CONTEXT_SWITCH_REQUESTED` → `CONTEXT_SWITCH_CONFIRMED`

---

### LAW 2: Single Gate Law

**Mandate**: ALL dangerous mutations MUST route through `AirlockModalV3`. NO direct API calls from UI controls.

**Implementation**:

- Mode changes, strategy halts, emergency stops → `openAirlock()`
- Every mutation MUST capture `state_before`, `state_after`, `dependencies`, `entry_exit_plan`
- Fast-path allowed for risk-reducing actions (e.g., STOP) but STILL gated

**Evidence Chain**:

```
SESSION_START → INTENT_CREATED → UI_OPENED → 
PREFLIGHT_CHECK → USER_CONFIRM_HELD → USER_CONFIRM_ACCEPTED → 
EXECUTE_REQUEST → EXECUTE_RESPONSE → BUNDLE_EXPORTED
```

---

### LAW 3: Fail-Closed + DEFCON Awareness

**Mandate**: System degradation MUST reduce capabilities, NEVER expand them.

**Implementation**:

- Any HTTP error MUST blur content + show RED banner with explicit error message
- Fallback to cached data MUST be visible (show `lastGoodTs`)
- DEFCON level MUST be visible in global header (OK / DEGRADED / HALT)
- HALT mode MUST disable ALL mutations (trading, withdrawals, config changes)

---

### LAW 4: Golden Thread (Provenance Everywhere)

**Mandate**: Every piece of live data MUST expose its provenance.

**Standard Format** (Provenance Footer):

```
REQ: ab12cd34 | LAT: 42ms | AGE: 3s | TS: 12:34:56 | SRC: network
```

**Required Fields**:

- `req_id`: Request identifier (8-char hash)
- `latency_ms`: Round-trip time
- `age_s`: Seconds since data timestamp
- `ts`: Data timestamp (HH:MM:SS)
- `source`: network | cache | sim | unknown

**Stale Data Rule**:

- Age > 10s → STALE badge + grey-out + status dot changes (🟢 → ⚪)
- Age > 60s → Data decay (strike-through)

---

### LAW 5: Anti-Hijack (Fingerprint + Anomaly Awareness)

**Mandate**: Session hijacking attempts MUST be detected and evidenced.

**Implementation**:

- Session fingerprint MUST include: browser, IP range, screen resolution, timezone
- Fingerprint mismatch → `ANOMALY_DETECTED` event → Airlock challenge
- Anomaly types: IMPOSSIBLE_TRAVEL, DEVICE_MISMATCH, IP_JUMP, TIMEZONE_SHIFT

---

### LAW 6: Physical Controls (Hold-to-Confirm + Safety Cover)

**Mandate**: Critical actions MUST require physical operator confirmation.

**Hold-to-Confirm Timing**:

- CRITICAL severity: 3.0s hold
- HIGH severity: 2.0s hold
- EMERGENCY (risk-reducing): 0.5-1.0s hold (fast-path)

**Safety Cover Pattern**:

- Two-step confirmation for irreversible actions (e.g., "Withdraw All")
- Example: Click "Withdraw" → Modal opens → Type amount → Hold-to-confirm → Execute

---

### LAW 7: Financial Draft Workflow

**Mandate**: High-value or governance-critical mutations MUST support draft → approval → execution.

**Workflow**:

```
USER creates draft → RISK_OFFICER reviews → 
COMPLIANCE approves → Airlock executes
```

**Evidence Steps**:

- `DRAFT_CREATED`, `REVIEW_REQUESTED`, `APPROVED`, `REJECTED`, `DRAFT_EXECUTED`

---

### LAW 8: Carve-Outs Evidenced

**Mandate**: Emergency overrides MUST be explicitly logged as `SYSTEM_SAFETY_ACTION`.

**Example Carve-Outs**:

- System-initiated circuit breaker (not user action)
- Automatic position liquidation (risk engine veto)
- Emergency downgrade (AUTO → MANUAL due to hard drift)

**Evidence Note**:

```tsx
recordEvent('SYSTEM_SAFETY_ACTION', {
  reason: 'Hard drift detected: 12.3% vs 0.1% threshold',
  action: 'Auto-downgrade: AUTO → MANUAL',
  triggered_by: 'RiskEngine'
});
```

---

### LAW 9: Blind Spots Declaration

**Mandate**: Known limitations MUST be explicitly declared in UI.

**Examples**:

- "This widget does not show cancelled orders"
- "Latency measurements exclude backend processing time"
- "Simulated data used for DEMO mode (not connected to live exchange)"

---

### LAW 10: Provenance Contracts

**Mandate**: All API responses MUST include provenance metadata.

**Backend Contract**:

```json
{
  "data": { ... },
  "meta": {
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "latency_ms": 42,
    "timestamp": 1706542800000,
    "source": "binance_live"
  }
}
```

If backend doesn't provide `meta`, frontend MUST synthesize minimal provenance (client-side latency, `source: 'unknown'`).

---

### LAW 11: Live Surfaces (No Hidden State)

**Mandate**: Operator MUST see all critical system state without navigating.

**Critical Surfaces** (must be visible without scroll):

- Current mode (MANUAL / SEMI / AUTO)
- DEFCON level
- Balance snapshot (total USD)
- Active strategies count
- Open positions count
- Recent errors / incidents
- UI heartbeat (LIVE / STALLED)

---

### LAW 12: Evidence Packs (Exportable Audit Trail)

**Mandate**: All evidence MUST be exportable as SHA-256 verified bundles.

**Bundle Structure**:

```json
{
  "bundle_id": "...",
  "session_id": "...",
  "events": [ ... ],
  "sha256": "..."
}
```

User can trigger export via `AirlockModalV3` → Export Evidence button.

---

### LAW 13: Auditor View (Read-Only Workspace)

**Mandate**: COMPLIANCE role MUST have read-only view of ALL actions.

**Implementation**:

- All Airlock events visible in Audit workspace
- No mutation controls in Audit workspace
- Evidence bundles downloadable by COMPLIANCE role

---

### LAW 14: Non-Custodial Stance

**Mandate**: UI MUST NOT store private keys, API secrets, or withdrawal addresses.

**Implementation**:

- All credentials stored in backend (encrypted at rest)
- Frontend receives bearer tokens only (short TTL)
- Private key operations delegated to backend HSM

---

### LAW 15: Black Box Survivability

**Mandate**: All forensic evidence MUST survive catastrophic failures.

**Implementation**:

- Evidence committed to backend on each step (not just at end)
- Session continuity across browser crashes
- Forensic session IDs persisted in localStorage + backend

---

## CRITICAL DEFINITIONS

### 1. DATA NOT CONNECTED vs MOCKED

**DATA NOT CONNECTED**:

- Widget attempts real API call but fails (404, 502, CORS, timeout)
- MUST show fail-closed banner: "DATA NOT CONNECTED - [error details]"
- MUST show `lastGoodTs` if available
- Example: "Last success: 12:34:56 (45s ago)"

**MOCKED / SIMULATED FOR DEMO**:

- Widget uses hardcoded or randomly generated data for demonstration
- MUST show explicit badge: "⚠️ MOCKED DATA - NOT CONNECTED TO LIVE EXCHANGE"
- MUST record in evidence: `source: 'sim'`
- Example: Preview mode, onboarding tour

**FORBIDDEN**:

- Silently falling back from live → sim without operator awareness
- Hiding connection errors behind generic "Loading..." spinners

---

### 2. FAIL-CLOSED VISUALS

**Mandatory Behavior on Error**:

1. **Blur widget content** (`backdropFilter: 'blur(4px)'`)
2. **Red banner overlay** with explicit error:
   - Error type (NonJsonResponseError, HttpError, NetworkError)
   - HTTP status (if applicable)
   - Content-Type (if mismatch)
   - Endpoint
   - Snippet (first 200 chars of response body)
3. **Show last good snapshot** (if available):
   - `lastGoodTs: 12:34:56 (45s ago)`
4. **Disable mutations** (if widget has controls)

**Example**:

```
┌─────────────────────────────────────────┐
│ [BLURRED BALANCES TABLE]                │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ ❌ DATA NOT CONNECTED             │ │
│  │ NON_JSON_RESPONSE                 │ │
│  │ HTTP 502: text/html               │ │
│  │ /api/balances                     │ │
│  │ "<html><body>502 Bad Gateway..."  │ │
│  │ Last success: 12:34:56 (45s ago)  │ │
│  └───────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

---

### 3. PROVENANCE STANDARD

**Format** (monospace for numbers):

```
REQ: ab12cd34 | LAT: 42ms | AGE: 3s | TS: 12:34:56 | SRC: network | EP: /balances
```

**Placement**:

- Widget footer (always visible, don't hide in mouse-over tooltips)
- Compact (single line, small font)

**Color Coding**:

- AGE < 10s: Normal color
- AGE 10-60s: Amber + STALE badge
- AGE > 60s: Red + DECAYED (strike-through data)

---

### 4. NO STALE DATA

**Stale Threshold**: 10 seconds (configurable per widget type)

**Visual Indicators**:

- Status dot: 🟢 (live) → ⚪ (stale) → 🔴 (error)
- Grey-out data (opacity: 0.6, greyscale filter)
- Strike-through values (text-decoration: line-through)
- STALE badge visible

**Behavior on Tab Return**:

- If tab was hidden > 10s → Force immediate refresh
- Show "Refreshing..." during fetch
- Never show

 stale data without warning

---

### 5. NO SILENT FALLBACKS

**FORBIDDEN**:

- Silently retrying failed requests without user awareness
- Falling back to cached data without showing cache age
- Using default values when API returns null/undefined
- Hiding errors behind eternal spinners

**REQUIRED**:

- Every fallback MUST be visible
- Every retry MUST be logged (max 3 retries)
- Every cache hit MUST show provenance (`source: 'cache'`, age)

---

### 6. DEAD MAN'S SWITCH

**UI Heartbeat Indicator**:

- Pulsing dot in global header (toggles every 500ms)
- If heartbeat stops → UI thread is blocked/frozen
- Detection: If last toggle > 1500ms → Show "UI STALLED" warning

**Implementation**:

```tsx
const [beat, setBeat] = useState(false);
useEffect(() => {
  const interval = setInterval(() => setBeat(b => !b), 500);
  return () => clearInterval(interval);
}, []);

// In header:
<div className={beat ? 'pulse-on' : 'pulse-off'}>
  {uiLive ? '🟢 UI LIVE' : '🔴 UI STALLED'}
</div>
```

**Evidence Recording**:

- If stalled detected → `recordEvent('SYSTEM_SAFETY_ACTION', { reason: 'UI heartbeat stalled' })`

---

## ENFORCEMENT

### Code Review Checklist

Before merging any UI PR, verify:

- [ ] All live widgets have Provenance Footer
- [ ] All errors show fail-closed banner (no silent failures)
- [ ] All mutations route through Airlock
- [ ] No direct API calls from onClick handlers
- [ ] Role-forbidden controls removed from DOM (not just disabled)
- [ ] Stale data shows STALE badge + grey-out
- [ ] localStorage keys prefixed with `workspace:${role}:`
- [ ] No hardcoded secrets, API keys, or private keys in frontend code

### Automated Lint Rules (TODO)

- Detect direct `fetch()` calls outside `/lib/api/` directory
- Detect `onClick={() => mutate()}` patterns (should use `openAirlock`)
- Detect `disabled={role !== 'ADMIN'}` patterns (should use conditional render)

---

## VERSIONING

**Current Version**: 1.0  
**Amendment Process**:

1. Propose amendment in `frontend/docs/ui_constitution_amendments.md`
2. Review by Frontend Architect + Governance Lead
3. Approval required from 2+ senior engineers
4. Update this document with version bump

**Change Log**:

- 2026-01-29 v1.0: Initial Constitution (15 Laws)

---

**CONSTITUTIONAL LOCK ENGAGED** 🔒  
This document governs all frontend development. Deviations require constitutional amendment.
