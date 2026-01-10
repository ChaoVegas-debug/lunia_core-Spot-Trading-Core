# UI Capability Inventory & Coverage Report (Ground Truth)

**Status**: FINAL_VERIFIED
**Date**: 2025-12-19
**Auditor**: Senior Implementation Agent

## 1. Route Inventory

| Route | Page Component | Guard | Role | Visible? | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/` | `LandingPage` | None | Public | Yes | ✅ Verified |
| `/register` | `RegisterPage` | None | Public | Yes | ✅ Verified |
| `/login` | `LoginPage` | None | Public | Yes | ✅ Verified |
| `/onboarding` | `OnboardingPage` | `ProtectedRoute` | USER+ | No | ✅ Verified |
| `/account` | `AccountPage` | `ProtectedRoute` | USER+ | Yes | ✅ Verified |
| `/account/subscription` | `SubscriptionPage` | `ProtectedRoute` | USER+ | Sub-nav | ✅ Verified |
| `/trader` | `TraderPanel` | `ReqOnboarding` | TRADER+ | Yes | ✅ Verified |
| `/portfolio` | `PortfolioPage` | `ReqOnboarding` | TRADER+ | Yes | ✅ Verified |
| `/risk` | `RiskPage` | `ReqOnboarding` | TRADER+ | Yes | ✅ Verified |
| `/strategies` | `StrategiesPage` | `ReqOnboarding` | TRADER+ | Yes | ✅ Verified |
| `/exchange-keys` | `ExchangeKeysPage` | `ReqOnboarding` | TRADER+ | Yes | ✅ Verified |
| `/fund` | `FundPanel` | `ProtectedRoute` | FUND+ | Yes | ✅ Verified |
| `/system` | `SystemPage` | `ProtectedRoute` | USER+ | Yes | ✅ Verified |
| `/docs` | `DocsPage` | `ProtectedRoute` | USER+ | Yes | ✅ Verified |
| `/getting-started` | `GettingStartedPage` | `ProtectedRoute` | USER+ | Yes | ✅ Verified |

## 2. Widget Inventory & Mounting Map

| Widget Name | Mounted In | Status | Notes |
| :--- | :--- | :--- | :--- |
| `ControlAuthorityBanner` | `TraderPanel.tsx` | ✅ Mounted | |
| `PortfolioRealityWidget` | `TraderPanel.tsx` | ✅ Mounted | |
| `ExecutionTimelineWidget` | `TraderPanel.tsx` | ✅ Mounted | |
| `RiskBudgetDashboardWidget` | `TraderPanel.tsx` | ✅ Mounted | Corrected location |
| `StrategyHealthWidget` | `TraderPanel.tsx` | ✅ Mounted | Corrected location |
| `StrategyVenueMappingWidget` | `TraderPanel.tsx` | ✅ Mounted | Corrected location |
| `RiskVetoExplanationPanel` | `TraderPanel.tsx` | ✅ Mounted | Corrected location |
| `TrustProgressWidget` | `AccountPage.tsx` | ✅ Mounted | |
| `AdminUserGovernanceOverrides` | `SystemPage.tsx` | ✅ Mounted | |
| `IncidentReplayView` | `SystemPage.tsx` | ✅ Mounted | |
| `GuidedOnboardingTour` | `App.tsx` | ✅ Mounted | |
| `AirlockModal` | `TraderPanel.tsx` | ✅ Mounted | **FIXED** (Was Dark) |
| `FlattenPortfolioModal` | `TraderPanel.tsx` | ✅ Mounted | **FIXED** (Was Dark) |

## 3. Gap Analysis & Resolution

### C0 Public
- [x] Landing page complete
- [x] Register page (Invite-only message + Demo seed)
- [x] Login (Honest errors)

### C1 Onboarding
- [x] Governance onboarding persistence (Verified `useOnboarding.ts` localStorage logic)
- [x] Route guard RequireOnboarding blocks Trader/Risk/Strategies
- [x] Demo mode bypass sets onboarding

### C2 Account
- [x] Profile read + honest "Edit disabled" (Verified in `AccountPage.tsx`)
- [x] TrustProgressWidget (Tier Visualization) ✅ (P3.3)
- [x] Plan limits card shows tier + limits
- [x] Subscription page (/account/subscription) ✅ (P2.4)

### C3 Trader Cockpit
- [x] SystemStateWidget
- [x] AirlockModal real diagnostics ✅ (Mounted in TraderPanel)
- [x] ControlAuthorityBanner ✅ (P3.1)
- [x] PortfolioRealityWidget ✅ (P3.1)
- [x] ExecutionTimelineWidget ✅ (P3.1)
- [x] GovernanceBanners drift detection
- [x] SystemHaltedOverlay
- [x] FlattenPortfolioModal ✅ (Mounted in TraderPanel)

### C4 Risk
- [x] RiskBudgetDashboardWidget ✅ (P3.2)
- [x] RiskVetoExplanationPanel ✅ (P3.2)

### C5 Strategies
- [x] StrategyHealthWidget ✅ (P3.2)
- [x] StrategyVenueMappingWidget ✅ (P3.2)

### C6 Admin
- [x] User Manager role edits
- [x] Feature flags toggle
- [x] AdminUserGovernanceOverrides ✅ (P3.4)
- [x] IncidentReplayView ✅ (P3.4)

## 4. Work Summary
*   **Audit Performed**: Scanned all routes and widgets.
*   **Fixes Applied**:
    *   Identified `AirlockModal` and `FlattenPortfolioModal` were unused (Dark Code).
    *   Mounted both modals in `TraderPanel.tsx`.
    *   Added "FLATTEN" (Danger) and "DIAGNOSTICS" (Secondary) buttons to the Trader Panel action header.
    *   Verified `useOnboarding` persistence logic.

System is now **100% Mounted** and **Code Verified**.
