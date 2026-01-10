# LUNIA Authentication & Access Lifecycle

## 1. Access Philosophy: Governance-First
LUNIA operates on a strict **Institutional Access Model**.
- **Public Registration**: **DISABLED**. There is no "Sign Up" button for the general public.
- **Access Method**: Invitation Only / Whitelist.
- **Identity Source**: Centralized User Database (Backend).

## 2. Authentication Flow

### A. Login (`/login`)
Standard JWT-based exchange.
1. **Input**: Email + Password.
2. **Action**: `POST /auth/login`
3. **Response**: `{ access_token, role, user_id, expires_at }`
4. **State Update**:
   - `bearerToken` set to `access_token`.
   - `role` updated from response.
   - `opsToken` set to `access_token` IF role is ADMIN (Heuristic).
5. **Post-Login Verification**:
   - Immediate call to `GET /auth/me` to fetch full profile (`UserProfile`).
   - If fail, user still logged in but with partial profile until refresh.

### B. "Registration" / Request Access (`/register`)
Since public registration is disabled, this page serves two purposes:

**Scenario 1: Production Mode**
- **UI**: Display "Access Restricted" message.
- **Action**: Directs user to contact Sales/Governance Committee.
- **No API Calls**.

**Scenario 2: Demo Mode** (`VITE_DEMO_MODE=1`)
- **UI**: Display "Launch Demo Environment" (Yellow Badge).
- **Action**: `POST /api/dev/seed-demo` (Requires internal hardcoded token).
- **Outcome**: 
  - Backend resets DB to known demo state.
  - Returns demo credentials (heuristic) or just success.
  - Frontend auto-fills or guides user to Login.

## 3. Token Management
Managed via `AuthContext` and unified `buildClient`.

| Token Type | Header | Purpose | Source |
| :--- | :--- | :--- | :--- |
| **Bearer** | `Authorization: Bearer <t>` | User Identity, Read Access | `/auth/login` |
| **Ops** | `X-OPS-TOKEN` | System Control (Start/Stop/Auto) | `/auth/login` (Admin) or Dev Injection |
| **Admin** | `X-Admin-Token` | User Management | `/auth/login` (Admin) |

## 4. Error Handling & Governance
- **401 Unauthorized**: Session Invalid -> Redirect to Login.
- **403 Forbidden**: Role Mismatch -> Show "Restricted Access".
- **503 Service Unavailable**: "Governance Engine Offline" -> Block Critical Actions (Airlock).

## 5. Onboarding Integration
After Login:
- User is redirected to `/trader` (Default).
- If `user.is_active` is false (or other logic), redirected to `/onboarding`.
- `/onboarding` is purely educational (Wizard) and does not modify backend state (unless `ack` endpoint exists, currently Client-Side only).

## 6. Known Gaps
- **2FA**: No backend verification. UI shows "Unavailable".
- **Real Registration**: No public endpoint exists.
- **Password Reset**: Manual process via Admin.
