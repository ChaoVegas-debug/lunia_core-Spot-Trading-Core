# Onboarding & Access Gating Logic

## 1. Governance Concept
Before accessing the Trading Cockpit (`/trader`), every institutional user MUST understand the governance constraints (Manual vs Semi vs Auto) and operational risks.
This educational flow is mandatory and persistent.

## 2. Onboarding Lifecycle
The onboarding state is user-specific.

### States
- **NOT_STARTED**: User has just registered. All trading routes GATED.
- **IN_PROGRESS**: User has started the wizard. Step is saved. Trading routes GATED.
- **COMPLETED**: User has finished Step 4. Access GRANTED.

### Route Protection
| Route | Protection | Behavior if Blocked |
| :--- | :--- | :--- |
| `/trader` | **LOCKED** | Redirect -> `/onboarding` |
| `/portfolio` | **LOCKED** | Redirect -> `/onboarding` |
| `/account` | **OPEN** | Shows "Onboarding Incomplete" Banner |
| `/onboarding` | **OPEN** | Main wizard (Resumes from saved step) |

## 3. Persistence Mechanism (Phase P0.2 GAP)
> [!IMPORTANT]
> Currently, onboarding status is persisted Client-Side via `localStorage`.
> **Key**: `LUNIA_ONBOARDING_{userId}`
> **Value**: `{ step: number, status: string }`

**Why?** The backend `/auth/me` endpoint does not yet return an `onboarding_status` field.
**Resolution**: When backend support is added, `useOnboarding` hook will be updated to fetch from API, migrating client-side state transparently.

## 4. Demo Mode Behavior
If `VITE_DEMO_MODE=1`:
1. User clicks "Launch Demo Environment" on Register Page.
2. System provisions a temporary Admin session.
3. **Auto-Complete**: The system automatically writes `status: 'COMPLETED'` to storage for this demo user.
4. User lands directly on `/trader`.

## 5. Resume Logic
- Reloading the page retains the current step.
- Logging out validates the session but retains the onboarding state for that User ID (unless cache cleared).
- Navigating away and back resumes linearly.
