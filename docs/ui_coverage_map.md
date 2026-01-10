# UI Coverage Map & Governance Contracts

## 1. Routes & Pages

| Route | Page Component | Access | Description |
| :--- | :--- | :--- | :--- |
| `/` | `LandingPage` | Public | Institutional overview, Venues, Plans. |
| `/login` | `LoginPage` | Public | Auth token exchange. |
| `/register` | `RegisterPage` | Public | Sign up form. |
| `/onboarding` | `OnboardingPage` | User | Wizard: Governance & Risk Education. |
| `/account` | `AccountPage` | User/Admin | Personal Cabinet: Identity, Security, Connectivity, Capital Setup. |
| `/trader` | `TraderPanel` | User/Admin | Main Cockpit: Control, Decision, Intelligence. |
| `/admin` | `AdminPanel` | Admin | Network Oversight, User Management, Global Kill Switch. |

## 2. Widget Coverage & Data Contracts

### 2.1 Control Plane
**SystemStateWidget**
- **Data**: `getOpsState` (Polling: 2.5s), `getHealth` (7s), `getStatus` (4s).
- **Source of Truth**: `ops.data.auto_mode`, `ops.data.global_stop`.
- **Actions**:
    - `setSystemMode('MANUAL'|'SEMI'|'STOP')`: Direct execution.
    - `setSystemMode('AUTO')`: **Strictly Gated** via `AirlockModal`.
    - `undoAction(token)`: Visible only if `ops.mode_change_token` (or response) exists.
- **Constraints**:
    - AUTO requires healthy API (Heartbeat OK, Latency < 1000ms).
    - GLOBAL STOP overrides everything (Hard Lock).

**CapitalControlsWidget**
- **Data**: `getOpsCapital` (Polling: 5s).
- **Source of Truth**: `global_cap_pct`.
- **Actions**: `setGlobalCapitalCap(pct)`.
- **Constraints**:
    - Backend prevents `cap_pct` > 100%.
    - Backend may reject if utilization is already above requested cap (Soft Lock).

**ExchangeControlsWidget** (Exchange Keys)
- **Data**: `getExchangeKeys`, `getExchanges`.
- **Actions**: `updateExchangeKeys`.
- **Constraints**: Keys are write-only on update. Read returns masked.

### 2.2 Decision Plane
**GovernanceBanners**
- **Data**: `getPortfolioSnapshot` (5s), `getBalances` (5s), `getOpsCapital` (5s).
- **Logic**: 
    - Drift: `Balance(Asset) < Portfolio(Asset) * 0.95`.
    - Capital: `usable_cap_pct < 0`.
- **Actions**: 
    - `handleReSync`: Soft reset (client-side data refresh).
    - `handleEmergencyStop`: Calls `setSystemMode('STOP')`.
    - `handleFix`: Open modal (Gap: User Guide).

**CreatePortfolioModal**
- **Contract**: Multi-step wizard.
- **Step 3 (AI)**: `analyzePortfolioDraft`. **Constraint**: Must succeed to unlock Step 4.
- **Step 4 (Exec)**: `createPortfolio`.

**AIProposalsWidget**
- **Data**: `getAiProposals`.
- **Actions**: `acknowledgeAiProposal(id, 'APPROVE'|'REJECT')`.

### 2.3 Intelligence Plane
**RiskWidget**
- **Data**: `getRisk`.
- **Fields**: `max_drawdown`, `max_exposure`, `sharpe_target`.

**LogsWidget**
- **Data**: `getLogs` (Polling: 3s).
- **Content**: Immutable audit stream.

## 3. Governance Rules & Failure States

1.  **Airlock Protocol (AUTO Mode)**
    - **Rule**: AUTO cannot be engaged if Diagnostics fail.
    - **Failure UX**: Modal blocks "Confirm" button. Shows Red X next to failed check (Latency/Status).

2.  **Position Drift**
    - **Rule**: Real-world balance matches Model.
    - **Failure UX**: Red Banner (Persistent).
    - **Resolution**: User must manually buy/sell on exchange OR "Re-Sync" if model is stale.

3.  **Capital Violation**
    - **Rule**: `usable_cap` must be positive.
    - **Failure UX**: Orange Banner "Downgraded to SAFE Mode".
    - **Resolution**: Increase Cap Limit or Deposit Funds.

4.  **Risk Veto**
    - **Rule**: Backend rejects orders exceeding risk params.
    - **Failure UX**: Toast "Order Rejected: Risk Veto (Reason)".

## 4. GAPS (Backend Missing)

| Feature | Missing Endpoint | Proposed Contract | Minimal UI Fallback |
| :--- | :--- | :--- | :--- |
| **Convert to Stable** | `POST /api/portfolio/emergency/liquidate` | `Body: { target: 'USDT' }` | Modal: "Feature requires backend. Please sell on exchange." |
| **Subscription Plan** | `GET /api/billing/plan` | `Res: { plan: 'PRO', status: 'ACTIVE' }` | UI: "PRO (Demo)" or "Contact Sales". |
| **2FA Setup** | `POST /auth/2fa/setup` | `Res: { secret: '...' }` | Toast: "2FA endpoints unavailable in this build." |
| **Fix Drift (Auto)** | `POST /api/portfolio/drift/fix` | `Res: { orders: [...] }` | "Fix on Exchange" Guide Modal. |
| **User Create/Edit**| `POST /admin/users` | - | Read-only list. |

## 5. Environment Flags
- `VITE_FRONTEND_FEATURE_AUTO_BETA_FOR_ALL`: Unlocks AUTO button.
- `VITE_DEMO_MODE`: Enables mock data for Subscription/Simulations.
