# Master UI Surface Extraction Map

**Objective:** 100% Surface Coverage of Backend Capabilities
**Principle:** If it's in `types.ts` or `previewStore`, it must be in the UI.

## 1. Core Operations (`OpsState`)

| Capability | Source Field | Current UI Surface | Status | Action Required |
| :--- | :--- | :--- | :--- | :--- |
| **System Mode** | `exec_mode` | TraderPanel (Cmd Strip) | [OK] | None |
| **Auto Mode** | `auto_mode` | TraderPanel (Cmd Strip) | [OK] | None |
| **Global Stop** | `global_stop` | TraderPanel (Cmd Strip) | [OK] | None |
| **Drift Status** | `drift_status` | TraderPanel (Banner) | [OK] | None |
| **Veto Reason** | `veto_reason` | TraderPanel (Halt Overlay) | [OK] | Ensure visible even if not halted (e.g. recent veto) |
| **Airlock Status** | `airlock_status` | SystemStateWidget (Banner) | [OK] | None |
| **Usable Cap** | `usable_cap_pct` | `OpsCapital` | CapitalControlsWidget | [OK] | None |
| **Last Drift Check** | `last_drift_check` | SystemStateWidget (Footer) | [OK] | None |

## 2. Trader Cockpit

| Capability | Source Field | Current UI Surface | Status | Action Required |
| :--- | :--- | :--- | :--- | :--- |
| **Manual Trade** | `executeManualTrade` | ManualTradeWidget | [OK] | Ensure Preview mode uses store |
| **Strategy Venues** | `StrategyVenueMapping` | TraderPanel | [OK] | Verify data population |
| **AI Proposals** | `AIProposal` | AIProposalsWidget | [OK] | None |
| **System Feed** | `ActivityResponse` | SystemFeedWidget | [OK] | None |

## 3. Portfolio Engine

| Capability | Source Field | Current UI Surface | Status | Action Required |
| :--- | :--- | :--- | :--- | :--- |
| **Active List** | `getPortfolioStructure` | PortfolioPage (List) | [OK] | Rich cards with PnL & Status |
| **Wizard** | `setPortfolioDraft...` | PortfolioPage (Wizard) | [OK] | Simulation fully wired |
| **Pause/Resume** | `runPortfolioAction` | PortfolioPage (Action Strip) | [OK] | Optimistic UI updates in SIM |
| **De-Risk** | `runPortfolioAction` | PortfolioPage (Action Strip) | [OK] | Scoped flatten simulation visible |
| **Rebalance** | `runPortfolioAction` | PortfolioPage (Action Strip) | [OK] | Action wired |
| **Detail Drawer** | `getPortfolioSnapshot` | PortfolioDetailDrawer | [NEW] | Full position & venue breakdown |

## 4. Strategy Engine

| Capability | Source Field | Current UI Surface | Status | Action Required |
| :--- | :--- | :--- | :--- | :--- |
| **Registry List** | `getStrategies` | StrategiesPage | [OK] | None |
| **Profile Switch** | `setStrategyProfile` | StrategiesPage (Top) | [OK] | None |
| **Performance** | `StrategyConfig` | StrategiesPage (Metrics) | [OK] | Bound to `metric_*` fields in store |
| **Orders View** | `SimOrder` | StrategyOrdersDrawer | [OK] | None |
| **Duplicate** | `duplicateStrategy` | DuplicateStrategyModal | [OK] | None |
| **Archive** | `archiveStrategy` | StrategiesPage (Btn) | [OK] | None |

## 5. Exchange Keys
 
 | Capability | Source Field | Current UI Surface | Status | Action Required |
 | :--- | :--- | :--- | :--- | :--- |
 | **List Keys** | `getExchangeKeys` | ExchangeKeysPage | [OK] | Rich table with status & redaction |
 | **Update Key** | `updateExchangeKeys` | Add/Edit Modal | [OK] | Fully simulated add/edit with audit |
 | **Test Connection** | `testExchangeConnection` | ExchangeKeysPage (Btn) | [OK] | Deterministic latency check |
 | **Delete Key** | `deleteExchangeKey` | ExchangeKeysPage (Btn) | [OK] | Honest confirmation & deletion |

## 6. Risk Engine

| Capability | Source Field | Current UI Surface | Status | Action Required |
| :--- | :--- | :--- | :--- | :--- |
| Capability | Source Field | Current UI Surface | Status | Action Required |
| :--- | :--- | :--- | :--- | :--- |
| **Global Mandates** | `getRiskMandates` | RiskPage (MandatesTable) | [OK] | Hard immutable limits |
| **Veto Log** | `getSystemEvents` | RiskPage (Log Tab) | [OK] | With remediation links |
| **Risk Metrics** | `getRiskDashboard` | RiskPage (DashboardWidget) | [OK] | Live exposure & leverage |
| **Policy Rules** | `getRiskRules` | RiskPage (RulesTable) | [OK] | Active rules with status |

## 7. Fund Management

| Capability | Source Field | Current UI Surface | Status | Action Required |
| :--- | :--- | :--- | :--- | :--- |
| **Overview** | `FundOverview` | FundPanel | [OK] | None |
| **Agg. Portfolio** | `FundPortfolio` | FundPanel (Widgets) | [OK] | None |
| **Strategy Perf** | `FundStrategy` | FundPanel (Table) | [OK] | None |

## 8. Admin & System Plane (`/admin`, `/system`)

| Capability | Source Field | Current UI Surface | Status | Action Required |
| :--- | :--- | :--- | :--- | :--- |
| **KPI Dashboard** | `getAdminStats` | AdminPage (Cards) | [OK] | None |
| **User Manager** | `getUsers` | AdminPage (Table) | [OK] | None |
| **System Cap** | `setGlobalCapitalCap` | SystemPage (Panel) | [OK] | None |
| **Event Stream** | `getSystemEvents` | SystemPage (Table) | [OK] | None |
| **Ops State** | `getOpsState` | SystemPage (Inspector) | [OK] | JSON Diagnostics added |

## 9. Account & Governance (Phase 4)

| Capability | Source Field | Current UI Surface | Status | Action Required |
| :--- | :--- | :--- | :--- | :--- |
| **User Profile** | `getUserProfile` | AccountPage | [OK] | None |
| **Trust Score** | `getTrustProfile` | AccountPage (Widget) | [OK] | None |
| **Plan Limits** | `requestUpgrade` | SubscriptionPage | [OK] | None |
| **Access Matrix** | `getPlan` | AccountPage | [OK] | None |

## 10. UX Cohesion & Improvements

| Feature | Description | Status | Action Required |
| :--- | :--- | :--- | :--- |
| **Navigation** | Top Level Links | Sidebar (Nav.tsx) | [OK] | Verified |
| **Empty States** | "No Strategies" etc | Various | [OK] | Using simulated data to avoid empty states |
| **Sim Labels** | "Preview Mode" badges | Global | [OK] | Enforced |

