# UI Wiring Map

All controls across panels (User/Trader/Fund/Admin/System) are mapped to concrete API endpoints with role guards and response handling.

| UI Control | Component/File | Method / Endpoint | Role | Success Schema | Error Handling | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Login submit | `frontend/src/pages/LoginPage.tsx` | POST `/auth/login` → GET `/auth/me` | All | `LoginResponse`, `UserProfile` | Inline alert + redirect on success | Wired |
| Tenant context selector | `frontend/src/components/layout/StatusStrip.tsx` | GET `/admin/tenants` (ADMIN) then sets `X-Tenant-Id` for subsequent calls | ADMIN | `{ items: Tenant[] }` | Select shows errors via DataStatus/stale chip | Wired |
| Auto On / Auto Off / Start All / Stop All | `ControlsWidget.tsx` | POST `/ops/auto_on`, `/ops/auto_off`, `/ops/start_all`, `/ops/stop_all` | TRADER/ADMIN | `OpsState` | Confirmation modal + alerts; audit log entry on result | Wired |
| System state polling | `SystemStateWidget.tsx` | GET `/ops/state`, `/status`, `/health` | All (guarded when required) | `OpsState`, `StatusSnapshot`, `HealthResponse` | DataStatus chips + stale banner | Wired |
| Activity feed | `SystemActivityWidget.tsx` | GET `/ops/activity` | Auth per telemetry | `ActivityResponse` | DataStatus + stale chip | Wired |
| Logs feed + UI audit | `LogsWidget.tsx` | GET `/ops/logs` + local UI audit stream | Auth per telemetry | `LogsResponse` | Alerts on failure, UI audit always available | Wired |
| Portfolio snapshot | `PortfolioWidget.tsx` | GET `/portfolio/snapshot` | Auth per telemetry | `PortfolioAggregate` | Alerts + stale indicator | Wired |
| Signals feed | `SignalsWidget.tsx` | GET `/ai/signals` | Auth per telemetry | `SignalsFeed` | Alerts + placeholder message | Wired |
| Risk + limits | `RiskWidget.tsx` | GET `/spot/risk`, `/admin/limits` | Auth per telemetry / ADMIN for limits | `SpotRiskConfig`, `{items: Limit[]}` | Alerts + warning banners | Wired |
| Capital snapshot | `CapitalWidget.tsx` | GET `/ops/capital` | Auth per telemetry | `CapitalSnapshot` | Alerts on failure | Wired |
| Feature flag toggle | `FeatureFlagsWidget.tsx` | PUT `/admin/flags/{key}` | ADMIN | `FeatureFlag` | Alerts + refresh | Wired |
| Limits upsert | `LimitsWidget.tsx` | PUT `/admin/limits` | ADMIN | `LimitEntry` | Alerts + refresh | Wired |
| User create/enable/disable | `AdminUsersWidget.tsx` | POST `/admin/users`, PUT `/admin/users/{id}` | ADMIN | `UserProfile` | Alerts + refresh | Wired |
| Tenant CRUD | `TenantsWidget.tsx` | GET/POST/PUT `/admin/tenants` | ADMIN | `TenantRecord` list/item | Alerts + status chip | Wired |
| Tenant branding update | `TenantsWidget.tsx` | GET/PUT `/admin/tenants/{id}/branding` | ADMIN | `TenantBranding` | Alerts + refresh | Wired |
| Tenant limits baseline | `TenantsWidget.tsx` | PUT `/admin/tenants/{id}/limits` | ADMIN | `{ items: Limit[] }` | Alerts + status chip | Wired |

All panels share these widgets; role gating hides or disables controls when the authenticated role lacks permission, and tenant context is propagated via `X-Tenant-Id`.
