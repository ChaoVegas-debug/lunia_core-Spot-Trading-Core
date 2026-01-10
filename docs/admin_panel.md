# Admin Panel Specification (P2.1)

## 1. Overview
The Admin Panel is a privileged area (`/admin`) for the Operator/SuperAdmin to observe and control the LUNIA SaaS. It adheres to **Governance Physics**: no unsafe bypasses, explicit audit trails for all actions, and "Honest UI" for missing backend capabilities.

## 2. Information Architecture (IA)

**Route**: `/admin/*`
**Guard**: `Role === 'ADMIN' | 'PROVIDER'`

| Path | Widget / Component | Data Source | Actions |
| :--- | :--- | :--- | :--- |
| `/admin` | `AdminOverviewWidget` | `/admin/overview` | None (Read-only) |
| `/admin/users` | `AdminUsersWidget` | `/admin/users` | Change Role, Disable (Mock) |
| `/admin/audit` | `AuditLogWidget` | `/admin/audit` | Filter by Action/Actor |
| `/admin/flags` | `FeatureFlagsWidget` | `/admin/flags` | Toggle Flags |
| `/admin/tenants` | `TenantsListWidget` | `/admin/tenants` | View Details |
| `/admin/exchanges` | `ExchangeHealthWidget` | `/spot/exchanges` | Aggregated View |

## 3. Component Details

### A. Admin Layout (`AdminLayout.tsx`)
- **Sidebar**: distinct from Trader Panel. Darker/"Operator" theme.
- **Header**: Shows "ADMIN MODE" badge.
- **Status Bar**: Global API Health, Redis status.

### B. Overview Dashboard
- **Cards**:
    - Active Users (Count)
    - System Health (OK/DEGRADED)
    - Active Tenants (Count)
    - Recent Alerts (List)

### C. Users Manager
- **Table**: ID, Email, Role, Last Login.
- **Actions**:
    - `Edit Role`: `POST /admin/users/:id/role`.
    - `Reset MFA`: (Honest UI: "Unavailable in Beta").

### D. Audit Log
- **Table**: Timestamp, Actor, Action, Result, Metadata.
- **Search**: Filter by `action` string.

### E. Feature Flags
- **List**: Key, Value, Updated At.
- **Edit**: Toggle boolean flags or edit string values.
- **Governance**: Changing a flag logs an Audit Event.

## 4. Governance & Safety
- **High Friction Actions**:
    - Editing User Roles or System Flags requires a **Confirmation Modal**.
    - "Kill Switch" (if exposed) requires **Typed Confirmation** ("STOP").
- **Audit**:
    - Frontend logs "Intent" if backend audit is partial.
    - All Write actions display a toast with the `Operation ID`.

## 5. Wiring Contract
- **Existing**: `getAdminOverview`, `getAdminUsers`, `getAdminAudit`, `getAdminFlags`, `updateUserRole`, `setAdminFlag`.
- **Gaps**:
    - `StrategiesRegistry`: Will reuse `/spot/strategies` but labeled as "System Default Strategies".
    - `Incidents`: Will filter `/ops/events` for severity `CRITICAL`.
