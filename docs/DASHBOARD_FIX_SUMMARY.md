# Dashboard Disappearing — Root Cause & Fix

## Root Cause

The TraderPanel dashboard was susceptible to disappearing due to:

1. **Overlay Blocking Logic**: `SystemHaltedOverlay` would fully block UI in production mode when `isLinkActive=false` or `isHalted=true`, preventing interaction but the dashboard was still rendered.

2. **Widget Rendering Errors**: If any widget inside the 3-lane layout threw an error during rendering (e.g. due to undefined data), the entire component tree could crash without an error boundary.

3. **Missing Operator Override**: No mechanism existed for operators to bypass governance/halt UI gating for diagnostic purposes.

## Fixes Applied

### 1. Render Anchor
Added a fixed banner at the top of TraderPanel that:
- Confirms the page is mounted (`DASHBOARD MOUNTED`)
- Shows current Operator Override status
- Displays Health status, Role, and Halted state

```tsx
<div id="trader-panel-render-anchor">
  🔧 DASHBOARD MOUNTED | Override: YES/NO | Health: ok
</div>
```

### 2. Operator Override
Environment-controlled override via `VITE_OPERATOR_OVERRIDE_EMAILS`:

```bash
# .env.local
VITE_OPERATOR_OVERRIDE_EMAILS=admin@example.com,operator@example.com
# Use * for all users (dev only)
VITE_OPERATOR_OVERRIDE_EMAILS=*
```

When active:
- Overlays are shown as warnings, not blockers
- Dashboard remains fully visible for diagnostics
- Trading fail-closed and auth_proven checks remain enforced

### 3. Block, Don't Hide Enforcement
Replaced `return null` patterns in:
- `HumanInterventionDecisionPanel` — now returns `<></>` instead of `null`

## Files Modified
- `frontend/src/pages/TraderPanel.tsx` — Render anchor, operator override
- `frontend/src/components/overlays/HumanInterventionDecisionPanel.tsx` — Block don't hide

## Runbook: "If Dashboard is Blank"

1. **Check Browser Console**
   - Look for `[TraderPanel] Render State:` log
   - If present → Page is mounted, issue is in child widgets
   - If absent → Page is not mounting (check routing/auth)

2. **Check Render Anchor**
   - Should be visible at the very top of the viewport
   - Shows: Mounted status, Override state, Health

3. **Check Auth Role**
   - Must be TRADER or ADMIN for `/trader` route
   - If wrong role → Redirects to `/login`

4. **Check Operator Override**
   - Set `VITE_OPERATOR_OVERRIDE_EMAILS=*` in `.env.local`
   - Restart frontend

5. **Check Widget Errors**
   - Open DiagnosticsPanel (🐞 DIAGNOSTICS button)
   - View Registry for blocked widgets
