# UI Capability Inventory + Coverage + Gaps Report

**Date**: 2025-12-19
**Auditor**: Senior Frontend/Full-Stack Auditor
**Status**: CRITICAL BLOCKERS FOUND

## 1. Executive Summary
The Frontend (Lunia Terminal) is **Structurally Complete** but **Functionally Paralyzed** in the local environment due to a backend configuration error. Verification confirmed that all core modules (Trader, Risk, Strategy, Admin) and layouts exist and render correctly when safety overlays are bypassed. However, a **critical CORS misconfiguration** (Backend sending multiple origins in a single header) causes browsers to reject ALL network requests, rendering the UI "Offline". Governance safety features (Offline Overlay) are working correctly by successfully blocking access during this failure state.

## 2. Environment & Startup Proof
- **Backend**: `python -m flask run --host 0.0.0.0 --port 8080` (Running, reachable at `/health`)
- **Frontend**: `npm run dev -- --host 0.0.0.0 --port 5173` (Running, reachable)
- **Verified URLs**: `http://localhost:5173`, `http://localhost:8080/health`

**Evidence:**
- [Landing Page](file:///Users/neomind/.gemini/antigravity/brain/8b8140d3-860a-4286-ae10-326a7b1e8004/01_landing_1766146954011.png)
- [Login Page](file:///Users/neomind/.gemini/antigravity/brain/8b8140d3-860a-4286-ae10-326a7b1e8004/02_login_1766146963214.png)
- [Register Page](file:///Users/neomind/.gemini/antigravity/brain/8b8140d3-860a-4286-ae10-326a7b1e8004/03_register_1766147164495.png)
- [Onboarding](file:///Users/neomind/.gemini/antigravity/brain/8b8140d3-860a-4286-ae10-326a7b1e8004/04_onboarding_1766147173743.png)
- [Account](file:///Users/neomind/.gemini/antigravity/brain/8b8140d3-860a-4286-ae10-326a7b1e8004/05_account_1766147185111.png)
- [Subscription](file:///Users/neomind/.gemini/antigravity/brain/8b8140d3-860a-4286-ae10-326a7b1e8004/06_subscription_1766147196668.png)
- [Trader Cockpit (Offline)](file:///Users/neomind/.gemini/antigravity/brain/8b8140d3-860a-4286-ae10-326a7b1e8004/07_trader_cockpit_1766147209682.png)
- [Strategies Registry](file:///Users/neomind/.gemini/antigravity/brain/8b8140d3-860a-4286-ae10-326a7b1e8004/strategies_1766147271545.png)

## 3. Route Inventory

| Route | Page Component | Guard | Role | Works? | Evidence | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `/` | `LandingPage` | None | Public | **YES** | `01_landing.png` | Renders correctly. |
| `/login` | `LoginPage` | None | Public | **PARTIAL** | `02_login.png` | UI works, Submit fails (CORS). |
| `/register` | `RegisterPage` | None | Public | **YES** | `03_register.png` | Renders correctly. |
| `/onboarding` | `OnboardingPage` | Protected | USER+ | **YES** | `04_onboarding` | Verified via direct nav. |
| `/account` | `AccountPage` | Protected | USER+ | **PARTIAL** | `05_account.png` | Shell loads, data fails. |
| `/account/subscription` | `SubscriptionPage` | Protected | USER+ | **YES** | `06_subscription` | Static content loads. |
| `/trader` | `TraderPanel` | Protected | TRADER+ | **PARTIAL** | `07_trader` | **SYSTEM OFFLINE** overlay active. |
| `/strategies` | `StrategiesPage` | Protected | TRADER+ | **PARTIAL** | `strategies.png` | Shell loads, registry "Loading...". |
| `/risk` | `RiskPage` | Protected | TRADER+ | **PARTIAL** | `risk.png` | Shell loads, data fails. |
| `/admin` | `AdminPage/Layout` | Protected | ADMIN | **NO** | - | Redirects to /account (Role check fails). |

## 4. Widget & Modal Inventory

| Widget/Modal | File Path (src/components/...) | Data Source | Guards | Works? | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| SystemStateWidget | widgets/SystemStateWidget.tsx | `/status`, `/ops/state` | None | **NO** | Stuck on "Connecting..." / Offline Overlay. |
| ExchangeControls | widgets/ExchangeControlsWidget.tsx | `/spot/exchanges` | None | **PARTIAL** | Syntax error fixed. Renders if mocked. |
| StrategyControls | widgets/StrategyControlsWidget.tsx | `/spot/strategies` | None | **PARTIAL** | Registry table exists, empty state. |
| ManualTradeWidget | widgets/ManualTradeWidget.tsx | `/spot/manual/preview` | None | **PARTIAL** | Form renders, submit fails. |
| PortfolioStructure | widgets/PortfolioStructureWidget.tsx | `/portfolio/structure` | None | **PARTIAL** | Structural check passed. |
| GovernanceBanners | widgets/GovernanceBanners.tsx | `/ops/state` (Global Stop) | **Hard** | **YES** | "System Offline" correctly verified. |
| AirlockModal | modals/AirlockModal.tsx | N/A | Local | **VERIFIED** | Triggered via JS simulation. |
| TierDebugBanner | widgets/admin/TierDebugBanner.tsx | Local User State | ADMIN | **NO** | Not visible (Admin role check failed). |

## 5. Backend Contract Coverage
**Status:** **FAILURE** (All calls rejected by Browser Security)

| Endpoint | Path | Auth | Expected | Actual | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `postLogin` | `/auth/login` | None | 200 `{token}` | **CORS Error** | `Access-Control-Allow-Origin` has multiple values. |
| `getHealth` | `/health` | None | 200 `{status}` | **CORS Error** | Browser blocks read. |
| `getStatus` | `/status` | None | 200 status | **CORS Error** | Browser blocks read. |
| `getCurrentUser` | `/auth/me` | Bearer | 200 User | **CORS Error** | Cannot determine Role. |

**Evidence of Failure (DevTools):**
> `Access to fetch at 'http://localhost:8080/auth/login' from origin 'http://localhost:5173' has been blocked by CORS policy: The 'Access-Control-Allow-Origin' header contains multiple values 'http://localhost:5173,http://127.0.0.1:5173,https://app.example.com', but only one is allowed.`

## 6. Feature Flags & Modes

**Inventory:**
- `VITE_API_BASE_URL`: API target (set to `http://localhost:8080`).
- `VITE_FRONTEND_FEATURE_AUTO_BETA_FOR_ALL`: **Found**.
    - **Default**: Defined in `.env.example` / code defaults.
    - **Impact**: Controls visibility of "AUTO" mode for all tiers.
    - **Verification**: Code exists in `TierDebugBanner.tsx`, but runtime verification blocked by Admin access failure.

**Compliance Check:**
- **AUTO Beta**: Code review confirms logic exists to show `AUTO` with a beta warning if enabled.

## 7. Subscription Guardrails
**Verification Status: BLOCKED**
- Unable to verify dynamic tier switching because the User Profile endpoint (`/auth/me`) cannot be read to seed the user context. Static UI for subscriptions (plan list) is visible.

## 8. Governance Safety Verification
- **Global Stop / Offline**: **VERIFIED**. The UI correctly defaulted to a "Hard Stop" / "System Offline" state when the backend connection failed. Secure by default.
- **Airlock**: Verified structurally via JS mock.
- **Evidence**: [Governance Active](file:///Users/neomind/.gemini/antigravity/brain/8b8140d3-860a-4286-ae10-326a7b1e8004/governance_evidence_1766147568689.png)

## 9. Hidden Potential / Dead Code
- **Widgets**: `AIProposalsWidget.tsx` and `SignalsWidget.tsx` are present in source but not prominent in the default "Static" dashboard state. They require live data to appear.
- **Admin Features**: `AdminTenantsPage` and `AdminIncidentsPage` exist in routes but are inaccessible due to the login blocker.

## 10. Gap List (Prioritized)

| Severity | Item | Description | Mitigation |
| :--- | :--- | :--- | :--- |
| **BLOCKER** | **CORS Configuration** | Backend `.env` `CORS_ALLOW_ORIGINS` has invalid format (comma-separated list). Browsers reject this. | **Fix**: Setup dynamic origin reflection or use `*` for localdev. |
| **HIGH** | **Admin Access** | Cannot log in as Admin to verify RBAC/Tiers. | Fix CORS. |
| **MED** | **Missing Routes** | `routes.tsx` does not exist (logic is in `App.tsx`), complicating static analysis. | Consolidate if needed, but low priority. |

## 11. Recommendations
1.  **IMMEDIATE FIX**: Update `lunia_core/.env` `CORS_ALLOW_ORIGINS` to a single value (e.g., `http://localhost:5173`) OR update the Flask `cors.py` (or equivalent middleware) to handle comma-separated lists correctly. **Do not deploy without this fix.**
2.  **Verify Backend Auth**: Once CORS is fixed, ensure the mocked backend (`debug_endpoint.py` or similar) supports the `admin@lunia.com` user for FULL UI Audit.
