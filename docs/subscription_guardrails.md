# Subscription Guardrails & Governance (v2.4)

## Overview
LUNIA operates on a tiered subscription model that strictly enforces governance barriers between Retail (Class C) and Institutional (Class A) capabilities. 
This document outlines the frontend enforcement mechanisms ("Guardrails") ensuring honest UI, clear upgrade paths, and strict compliance.

## Tier Structure
| Tier | ID | Cap Limit | Exchanges | Portfolios | Algo/Auto | Risk Profiles |
|------|----|-----------|-----------|------------|-----------|---------------|
| Beginner | `BEGINNER` | $10k | 1 | 1 | ❌ | Balanced |
| Standard Retail | `STD_RETAIL` | $50k | 3 | 3 | ❌ | + Shield |
| Advanced Retail | `ADV_RETAIL` | $250k | 5 | 10 | ✅ | + Aggressive |
| Institutional | `INST_LITE` | Unlimited | Unlimited | Unlimited | ✅ | + Rocket (Full) |

## Enforcement Mechanisms

### 1. Honest UI Policy
- **No Fake Billing**: We do not collect payments in the app.
- **Request Flow**: All "Upgrade" actions trigger a `RequestUpgradeModal` aimed at collecting intent (Lead Gen).
- **Transparency**: Users are told exactly *why* a feature is locked (e.g., "Risk Profile Restricted due to volatility governance") and *what* plan is required to unlock it.

### 2. Lock & Gating Patterns
#### Standard Lock Modal
A standardized `LockedFeatureModal` is used across the application:
- **Triggers**: Clicking a locked feature (e.g., AUTO button, Rocket Profile).
- **Content**: Title, Explanation, Required Tier, "Request Upgrade" Call-to-Action.

#### Limit Checks
- **Exchange Limits**: Checked in `ExchangeControlsWidget`.
- **Portfolio Limits**: Checked in `CreatePortfolioModal`.
- **Capital Limits**: Checked passively (backend rejection) or via UI warnings.

#### Governance Veto (Risk)
- **Risk Profiles**: High-volatility profiles (e.g., ROCKET) are strictly gated to Institutional plans.
- **Auto Mode**: Autonomous trading is gated to `ADV_RETAIL` and above, with a **Beta Override** available via `VITE_FRONTEND_FEATURE_AUTO_BETA_FOR_ALL`.

### 3. Admin Tools
- **Simulation**: Admins can use the `AdminSubscriptionWidget` to hot-swap their session tier to test different user experiences instantly.
- **Debug Banner**: A visible banner shows the active simulated tier and critical feature flags (Auto Allowed, Beta Flag) to prevent confusion during testing.

## Integration Points
- **Plan Definitions**: `src/domain/subscription/plans.ts`
- **Auth/Session**: `src/hooks/useAuth.tsx`
- **Widgets**: `SystemStateWidget` (Auto), `CreatePortfolioModal` (Portfolios/Risk), `ExchangeControlsWidget` (Exchanges).
