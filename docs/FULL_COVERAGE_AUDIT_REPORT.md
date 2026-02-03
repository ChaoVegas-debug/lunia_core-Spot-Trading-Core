# LUNIA/ALADDIN Full Coverage Forensic Audit Report

**Generated:** 2026-01-16T19:45 UTC+1  
**Branch:** variant-a-systemmode-runmode  
**Commit:** 86ce0c0d618d40e4768617fb2887c54592f03638  
**Dirty Files:** 82 (0 modified, 0 untracked - all staged)

---

## 1. EXECUTIVE SUMMARY

| Metric | Value | Status |
|--------|-------|--------|
| Backend Endpoints | 82 | ✅ |
| Frontend Routes | 15+ protected | ✅ |
| Adapter Exports | 60+ | ✅ |
| UI Widgets | 40+ | ✅ |
| Modals | 11 | ✅ |
| Direct fetch() bypasses | **0** | ✅ SAFE |
| tryRealOrFallback refs | 141 | ✅ GATED |
| require_role decorators | 40+ | ✅ |
| exec_mode === 'real' | 0 | ✅ FIXED |

### Verdict: **GOVERNANCE-SAFE WITH 1 P0 FINDING**

---

## 2. ROUTES & RBAC TABLE

| Route | Component | Allowed Roles | Enforcement |
|-------|-----------|---------------|-------------|
| `/login` | LoginPage | PUBLIC | None |
| `/register` | RegisterPage | PUBLIC | None |
| `/` | LandingPage | PUBLIC | None |
| `/account` | AccountPage | USER, TRADER, FUND, ADMIN | ProtectedRoute |
| `/account/subscription` | SubscriptionPage | USER, TRADER, FUND, ADMIN | ProtectedRoute |
| `/trader` | TraderPanel | TRADER, ADMIN | ProtectedRoute |
| `/portfolio` | PortfolioPage | TRADER, ADMIN | ProtectedRoute |
| `/risk` | RiskPage | TRADER, ADMIN | ProtectedRoute |
| `/strategies` | StrategiesPage | TRADER, ADMIN | ProtectedRoute |
| `/exchange-keys` | ExchangeKeysPage | TRADER, ADMIN | ProtectedRoute |
| `/fund` | FundPanel | FUND, ADMIN | ProtectedRoute |
| `/system` | SystemPage | ALL AUTH | ProtectedRoute |
| `/docs` | DocsPage | ALL AUTH | ProtectedRoute |
| `/getting-started` | GettingStartedPage | ALL AUTH | ProtectedRoute |
| `/intelligence` | IntelligenceDashboard | TRADER, ADMIN, FUND | ProtectedRoute |
| `/admin/*` | AdminLayout | ADMIN | ProtectedRoute |

**Evidence:** `frontend/src/App.tsx:56-200`

---

## 3. UI SURFACE INVENTORY (HIGH-RISK)

| Widget | Adapter Function | Backend Endpoint | SIM Fallback | Risk Level |
|--------|------------------|------------------|--------------|------------|
| ManualTradeWidget | executeManualTrade | /spot/manual/execute | ✅ YES | **TRADE** |
| StartConfirmationModal | opsStart | /ops/start | ✅ YES | **STATE** |
| SystemStateWidget | setSystemMode | /api/system/mode | ✅ YES | STATE |
| BalancesWidget | getBalances | /api/exchange/balances | ✅ YES | READ |
| PortfolioStructureWidget | runPortfolioAction | /api/portfolios/action | ✅ YES | STATE |
| ExchangeKeysPage | updateExchangeKeys | /api/exchanges/keys | ✅ YES | STATE |
| AIProposalsWidget | acknowledgeAiProposal | /ai/proposals/ack | ✅ YES | STATE |

**All UI widgets use adapter → tryRealOrFallback → simulatedBackend fallback**

---

## 4. ADAPTER ↔ BACKEND MATRIX

### 4.1 Trade Execution Paths

| Adapter Function | Backend Endpoint | RBAC | Governance Check | Status |
|------------------|------------------|------|------------------|--------|
| `opsStart` | /ops/start | TRADER/ADMIN | ✅ global_stop, airlock, live_allowed, live_confirmed | **SAFE** |
| `executeManualTrade` | /spot/manual/execute | TRADER/ADMIN | ⚠️ **MISSING** global_stop check | **P0** |
| `previewManualTrade` | /spot/manual/preview | TRADER/ADMIN | ✅ Preview only | SAFE |

### 4.2 Mode/State Changes

| Adapter Function | Backend Endpoint | Status |
|------------------|------------------|--------|
| `setSystemMode` | /api/system/mode | ✅ |
| `setGlobalCapitalCap` | /api/capital/set-cap | ✅ |
| `setStrategyProfile` | /api/strategies/set-profile | ✅ |
| `haltStrategies` | /api/strategies/halt | ✅ |
| `runPortfolioAction` | /api/portfolios/{id}/action | ✅ |

### 4.3 Admin Operations

| Adapter Function | Backend Endpoint | Status |
|------------------|------------------|--------|
| `getAdminStats` | /admin/overview | ✅ |
| `getUsers` | /admin/users | ✅ |
| `updateUserRole` | /admin/users/{id}/role | ✅ |
| `getAdminFlags` | /admin/flags | ✅ |

---

## 5. HIGH-RISK FINDINGS

### P0-001: `/spot/manual/execute` Missing Governance Checks

**File:** `lunia_core/app/services/api/flask_app.py:1994-2020`

**Evidence:**
```python
@app.post("/spot/manual/execute")
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
@safety_guard
def manual_trade_execute() -> Any:
    body = request.get_json(force=True) or {}
    proposal = body.get("proposal", {})
    confirmed = body.get("confirmed", False)
    
    if not confirmed:
        return jsonify({"error": "Confirmation required"}), 400
    # ... NO global_stop / airlock / run_mode CHECK
```

**Missing:**
- `global_stop` check
- `airlock_status` check  
- `run_mode` check (should only work if run_mode == 'real')

**Severity:** P0 - Trading can proceed even if `global_stop == true`

---

## 6. ADMIN COVERAGE

| Domain | UI Page | Adapter | Backend | E2E |
|--------|---------|---------|---------|-----|
| Users | AdminUsersPage | getUsers, updateUserRole | /admin/users | ✅ |
| Audit | AdminAuditPage | getAudit | /admin/audit | ✅ |
| Flags | AdminFlagsPage | getAdminFlags | /admin/flags | ✅ |
| Tenants | AdminTenantsPage | getTenants | /admin/tenants | ⚠️ Partial |
| Incidents | AdminIncidentsPage | - | - | ❌ No backend |
| Exchanges | AdminExchangesPage | testExchangeConnection | /api/exchanges/test | ✅ |

---

## 7. GAP LIST

### P0 — Security / Governance

| ID | Title | Evidence | Missing | Backend Exists |
|----|-------|----------|---------|----------------|
| P0-001 | Manual Execute Missing Governance | flask_app.py:1994 | global_stop/airlock check | YES |

### P1 — Missing UI Surface

| ID | Title | Evidence | Missing | Backend Exists |
|----|-------|----------|---------|----------------|
| P1-001 | AI Run Endpoint | flask_app.py:2187 | No UI trigger | YES |
| P1-002 | Incidents Backend | AdminIncidentsPage | Backend missing | NO |

### P2 — UX / Completeness

| ID | Title | Evidence | Missing |
|----|-------|----------|---------|
| P2-001 | Tenant branding in UI | AdminTenantsPage | Full config editor |
| P2-002 | Strategy marketplace | StrategyMarketplace.tsx | Backend missing |

---

## 8. PROMPT 2/2 — FINAL DECISION

### Does UI fully cover implemented backend? **YES (with 1 gap)**

Evidence: All 60+ adapter functions have SIM fallback. All high-risk paths go through adapter.

### Is governance fully FAIL-CLOSED? **NO — 1 P0 Blocker**

Evidence: `/spot/manual/execute` at flask_app.py:1994 does NOT check `global_stop` before execution.

---

## 9. BACKLOG FOR CLOSURE

### P0-001: Add Governance Gates to Manual Execute

**File:** `lunia_core/app/services/api/flask_app.py:1994`

**What is missing:**
```python
# MUST ADD at line ~2000:
state = get_runtime_state()
if state.get("global_stop", True):
    return jsonify({"error": "Trading halted", "code": "GLOBAL_STOP"}), 403
    
run_state = state.get("run_state", {})
if run_state.get("run_mode") != "real":
    return jsonify({"error": "Not in REAL mode", "code": "DRY_MODE"}), 403
```

**Adapter needed?** NO  
**Backend exists?** YES  
**Acceptance criteria:**
1. `grep -n "global_stop" lunia_core/app/services/api/flask_app.py | grep manual` returns line
2. Manual trade blocked when global_stop=true
3. Manual trade blocked when run_mode='dry'

---

**END OF AUDIT REPORT**
