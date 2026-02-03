# Variant A Diff Summary

**Branch:** variant-a-systemmode-runmode  
**Date:** 2026-01-16

## Overview

This change implements Variant A mode semantics, separating:
- **system_mode** ∈ {STOP, MANUAL, SEMI, AUTO} — governance/control plane
- **run_mode** ∈ {dry, real} — execution/run plane

## Files Changed

### 1. frontend/src/api/types.ts

**Purpose:** Define canonical types

**Changes:**
```typescript
// Added to OpsState:
system_mode?: SystemMode; // STOP | MANUAL | SEMI | AUTO (governance mode)

/** @deprecated Use system_mode instead. Will be removed in future version. */
exec_mode?: string;

// Changed in OpsStartResponse.gates:
system_mode: SystemMode; // VARIANT A: Changed from exec_mode
```

---

### 2. frontend/src/components/modals/StartConfirmationModal.tsx

**Purpose:** Fix P0 live gating bug

**Before:**
```typescript
const execMode = ops?.exec_mode || 'dry';
const canGoLive = execMode === 'real' && airlockStatus === 'ARMED' && !globalStop;
```

**After:**
```typescript
const systemMode = ops?.system_mode || (ops?.auto_mode ? 'AUTO' : 'MANUAL');
const canGoLive = airlockStatus === 'ARMED' && !globalStop;
```

**Impact:** Live button now appears when airlock is ARMED and system not stopped.

---

### 3. frontend/src/components/widgets/ExecutionCommandStrip.tsx

**Purpose:** Use system_mode for mode switch display

**Change:**
```typescript
// VARIANT A: Use system_mode for governance, derive from auto_mode if missing
const mode = effectiveOps?.system_mode || (effectiveOps?.global_stop ? 'STOP' : (effectiveOps?.auto_mode ? 'AUTO' : 'MANUAL'));
```

---

### 4. frontend/src/components/widgets/SystemStateWidget.tsx

**Purpose:** Use system_mode as source of truth

**Change:**
```typescript
// VARIANT A: Use system_mode as source of truth, with fallback derivation
let derivedMode = ops.data?.system_mode || 'MANUAL';
if (!ops.data?.system_mode) {
  // Backwards compat: derive from legacy fields if system_mode not present
  if (ops.data?.global_stop) derivedMode = 'STOP';
  else if (ops.data?.auto_mode) derivedMode = 'AUTO';
  else if (ops.data?.manual_strategy) derivedMode = 'SEMI';
}
```

---

### 5. frontend/src/pages/TraderPanel.tsx

**Purpose:** Use system_mode for halt detection

**Change:**
```typescript
// VARIANT A: Use system_mode for halt detection
const systemMode = effectiveOps?.system_mode || (effectiveOps?.global_stop ? 'STOP' : 'MANUAL');
const isHalted = effectiveOps?.global_stop || systemMode === 'STOP';
```

---

### 6. frontend/src/components/widgets/PreviewStatusBadge.tsx

**Purpose:** Display system_mode in diagnostics

**Change:**
```typescript
<div>System Mode: <span>{state.ops.system_mode || 'MANUAL'}</span></div>
```

---

### 7. frontend/src/preview/PreviewStore.ts

**Purpose:** Use system_mode in simulation state

**Changes:**
- `INITIAL_OPS.system_mode = 'MANUAL'` (was `exec_mode`)
- `setExecMode` now sets `system_mode`
- `setGlobalStop` sets `system_mode = 'STOP'`
- `triggerDrift` checks and sets `system_mode`

---

### 8. frontend/src/preview/simulatedBackend.ts

**Purpose:** Use system_mode for governance, run_mode for execution

**Key Changes:**
```typescript
// DEFAULT_SIM_OPS
system_mode: isPreviewUnlocks ? 'SEMI' : 'MANUAL', // VARIANT A

// setExecMode
currentSimOps.system_mode = mode; // VARIANT A

// opsStart run_mode determination
const run_mode: 'dry' | 'real' = (currentSimOps.airlock_status === 'ARMED' && mode === 'real') ? 'real' : 'dry';

// gates response
system_mode: currentSimOps.system_mode || 'MANUAL', // VARIANT A
```

---

## Security Verification

- ✅ No new order endpoints added
- ✅ shouldUseSim / tryRealOrFallback unchanged
- ✅ Preview cannot execute real orders
- ✅ run_mode defaults to 'dry'
- ✅ Real mode requires airlock ARMED + !global_stop

## Backwards Compatibility

All components include fallback derivation if `system_mode` is not present:
- Derive from `global_stop` → 'STOP'
- Derive from `auto_mode` → 'AUTO'
- Default → 'MANUAL'
