# Variant A Pre-Change Evidence Document

**Generated:** 2026-01-16T19:12 UTC+1  
**Branch:** variant-a-systemmode-runmode  
**Base Commit:** 86ce0c0d618d40e4768617fb2887c54592f03638

## Repo Identity

```
Path: /Users/neomind/alladin/lunia_core-Spot-Trading-Core
HEAD: 86ce0c0d618d40e4768617fb2887c54592f03638
Dirty Files: 76 total (45 modified, 31 untracked)
```

## Grep Counts (Post-Implementation)

| Pattern | Frontend Count | Notes |
|---------|---------------|-------|
| `exec_mode` | 3 | 2 in types.ts (deprecated field + comment), 1 in simulatedBackend.ts (comment) |
| `system_mode` | 30 | Canonical governance mode field |
| `run_mode` | 13 | Canonical execution mode field |
| `exec_mode === 'real'` | **0** | P0 FIXED - no incorrect gating |
| `execMode === 'real'` | **0** | P0 FIXED - no incorrect gating |

## Remaining exec_mode References (All Safe)

1. `frontend/src/api/types.ts:75` - Deprecated field definition with JSDoc
2. `frontend/src/api/types.ts:149` - Comment documenting change
3. `frontend/src/preview/simulatedBackend.ts:585` - Comment explaining logic

## Files Modified for Variant A

| File | Changes |
|------|---------|
| frontend/src/api/types.ts | Added `system_mode: SystemMode` to OpsState, deprecated `exec_mode`, updated OpsStartResponse.gates |
| frontend/src/components/modals/StartConfirmationModal.tsx | **P0 FIX**: canGoLive now uses airlock_status + !global_stop |
| frontend/src/components/widgets/ExecutionCommandStrip.tsx | Uses system_mode with fallback |
| frontend/src/components/widgets/SystemStateWidget.tsx | Uses system_mode as source of truth |
| frontend/src/pages/TraderPanel.tsx | Uses system_mode for halt detection |
| frontend/src/components/widgets/PreviewStatusBadge.tsx | Displays system_mode |
| frontend/src/preview/PreviewStore.ts | Uses system_mode instead of exec_mode |
| frontend/src/preview/simulatedBackend.ts | Uses system_mode for governance, run_mode for execution |

## Invariants Status

All 9 LOCKED invariants remain intact:
1. ✅ FAIL-CLOSED governance model
2. ✅ global_stop overrides everything (73 refs)
3. ✅ Airlock 5-step protocol (24 refs)
4. ✅ Drift → PAUSE logic
5. ✅ No orders in PREVIEW/SIM/DRY
6. ✅ Tier gating 4 tiers
7. ✅ Human-in-the-loop
8. ✅ No auto-resume after emergency
9. ✅ Blockchain Truth is Absolute
