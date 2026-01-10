# UI Coverage Map V2 (Phase P2.0)

**Governance Principle**: Honest UI. If backend has it, we show it. If backend lacks it, we show "Unavailable".

## 1. Trader Cockpit (`/trader`)

| Widget | Data Source | Actions | Verification Status | Gaps / To-Do |
| :--- | :--- | :--- | :--- | :--- |
| **SystemState** | `/ops/state`, `/health` | Mode (Manual/Semi/Auto), Stop, Flatten | 🟢 Good | Undo Added. Offline Block Added. |
| **CapitalControlsWidget** | `/ops/capital` | Set Cap | 🟢 Good | Verified. |
| **ExchangeControlsWidget** | `/spot/exchanges` | Enable/Disable, Alloc | 🟢 Good | Reconnect CTA Added. |
| **StrategyControlsWidget** | `/spot/strategies` | Enable/Disable, Weight | 🟢 Good | Empty State & Badges Added. |
| **SystemFeed** | `/ops/events`? | None (Read-only) | ⚪ Unknown | Check if using `/ops/events` or `/ops/activity`. |
| **PortfolioStructureWidget** | `/portfolio`, `/portfolio/structure` | None | 🟡 Partial | Visuals for "Drift" needed here? |
| **Risk** | `/spot/risk` | None (Read-only) | 🟢 Good | Verify real data populated. |
| **ManualTradeWidget** | `/spot/manual/*` | Preview, Execute | 🟢 Good | Preview flow refined. |
| **ManualTradeWidget** | `/spot/manual/*` | Preview, Execute | 🟢 Good | Preview flow refined. |
| **Intelligence** | `/ai/signals`? | None | ⚪ Unknown | Replaced by SignalsWidget? |
| **SignalsWidget** | `/ai/signals`, `/arbitrage` | View Signals & Arb | 🟢 Good | Surfaced in P2.3. |
| **AIProposalsWidget** | `/ai/proposals` | Acknowledge/Execute | 🟡 Partial | Verify "Empty" state is friendly. |
| **Logs** | `/ops/logs` | None | 🟢 Good | Auto-scroll check. |

## 2. Hidden Capabilities (Surfaced in P2.3)

| Capability | Backend | Surfaced Location |
| :--- | :--- | :--- |
| **Arbitrage Opps** | `/arbitrage/opps` | **Trader**: Right Lane (Signals Widget). |
| **AI Signals** | `/ai/signals` | **Trader**: Right Lane (Signals Widget). |
| **Admin Nav** | `/admin/*` | **Admin**: Dashboard Grid. |
| **Undo Actions** | `UndoToken` headers | **Done**: Added to SystemState & Strategy Widgets. |
| **Audit Log** | `/admin/audit` | Distinct from "Logs". |
| **AI Portfolio Analysis** | `/api/ai/analyze-portfolio` | `CreatePortfolioModal` Step 2. |

## 3. Account / Cabinet (`/account`)

| Section | Status | Needs |
| :--- | :--- | :--- |
| **Identity** | 🟢 Good | Role displayed. |
| **Security** | 🟢 Honest | 2FA Unavailable message added. |
| **Exchange Keys** | 🟢 Good | Real status chips added. |

## 4. Onboarding (`/onboarding`)

- **Status**: 🟢 Verified (P0.3).
- **Check**: Ensure "Demo Seed" is only available here.

- **Status**: 🟢 Verified (P0.1).

## 6. Admin Panel (`/admin`) - P2.1

| Page | Data Source | Capabilities | Coverage |
| :--- | :--- | :--- | :--- |
| **Dashboard** | `/admin/overview` | Metrics (Users, Tenants, Health) | 🟢 Good |
| **Users** | `/admin/users` | List, Role Edit Use | 🟢 Honest |
| **Audit** | `/admin/audit` | Immutable Log Viewer | 🟢 Good |
| **Flags** | `/admin/flags` | View/Toggle System Flags | 🟢 Good |
| **Tenants** | `/admin/tenants` | List Tenants | 🟡 Partial (Read-only) |
| **Incidents** | `/ops/events` | Timeline of Critical Events | 🟢 Good |
| **Exchanges** | `/spot/exchanges` | Global Aggregated Health | 🟢 Good |
### Phase 2: Governance & Admin
- [x] **P2.1 Admin Panel**: `AdminDashboard.tsx`, `AdminSubscriptionWidget.tsx` (Simulator)
- [x] **P2.2 Subscription Guardrails**: 
  - `SystemStateWidget.tsx`: Auto Mode Gating + Beta Override Banner.
  - `CreatePortfolioModal.tsx`: Portfolio Count Limit (Safe) + Risk Profile Gating.
  - `ExchangeControlsWidget.tsx`: Exchange Count Limit.
  - `AccountPage.tsx`: Plan Limits Card.
- [ ] **P2.3 Audit**: `GovernanceBanners.tsx` (Strict Mode)

## 7. Subscription Guardrails (`/account` & `/trader`) - P2.2

| Section | Feature | Guardrail | Status |
| :--- | :--- | :--- | :--- |
| **Cabinet** | Plan Display | Honest UI (Backend or Default) | 🟡 In-Progress |
| **Cabinet** | Limits | Visual usage bars | 🟡 In-Progress |
| **Cabinet** | Upgrade | Sales Contact Modal | 🟡 In-Progress |
| **Subscription Page** | New Page | Comparison Table, Upgrade Flow | 🟢 Good |
| **Subscription Modals** | New Modals | Upgrade/Downgrade, Cancel | 🟢 Good |
| **Trader** | Auto Mode | Block if Plan < Pro (Beta Override Exception) | 🟡 In-Progress |
| **Trader** | Risk Profiles | Block Aggressive/Rocket for Low Tiers | 🟡 In-Progress |
| **Trader** | Exchange Count | Block if > Plan Limit | 🟡 In-Progress |
```
