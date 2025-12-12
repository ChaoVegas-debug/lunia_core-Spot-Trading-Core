# White-label / SaaS Readiness

This project supports tenant-aware branding and admin-led white-label management without altering trading logic or the API contract.

## Current capabilities
- Tenant resolution precedence: `X-Tenant-Id` header → host domain match → fallback to `DEFAULT_TENANT_SLUG`.
- Public branding payload exposed at `/branding` with: `brand_name`, `logo_url`, `support_email`, `primary_color`, `environment`, `tenant_id` (from resolved tenant).
- Login responses and `/auth/me` surface `tenant_id` so frontend can render tenant-aware chrome and restrict cross-tenant access (non-admin users must match the resolved tenant).
- Frontend reads branding defaults from environment (`VITE_BRAND_*`) and falls back to `/branding`.
- Admin-only tenant management endpoints:
  - `GET /admin/tenants` — list tenants, domains, status.
  - `POST /admin/tenants` — create tenant (slug, name, status, branding fields, domains).
  - `PUT /admin/tenants/{id}` — update tenant core fields/domains.
  - `GET/PUT /admin/tenants/{id}/branding` — manage branding payloads.
  - `PUT /admin/tenants/{id}/limits` — set tenant baseline limits (stored in `limits` table scope=tenant).
  - All mutations are audited and RBAC = ADMIN.
- Frontend Admin panel includes a Tenants tab for list/create/edit/branding/limits with live preview in the status strip; ADMINs
  can switch tenant context (sets `X-Tenant-Id`) from the status strip.

## Configuration
Set in `lunia_core/.env` (or via environment variables):
- `DEFAULT_TENANT_SLUG` (fallback tenant, default `default`)
- `BRAND_NAME` (required)
- `BRAND_PRIMARY_COLOR` (optional)
- `BRAND_LOGO_URL` (optional)
- `BRAND_SUPPORT_EMAIL` (optional)
- `BRAND_ENVIRONMENT` (dev/stage/prod string)

Frontend overrides (optional) in `frontend/.env`:
- `VITE_BRAND_NAME`, `VITE_BRAND_LOGO`, `VITE_BRAND_SUPPORT`, `VITE_BRAND_PRIMARY_COLOR`, `VITE_TENANT_ID`

## Next steps for full multi-tenancy
- Extend portfolio/execution isolation per tenant (current scope covers auth/admin/branding/limits only).
- Add per-tenant API keys and optional asset storage for logos if binary uploads are needed.
- Enforce tenant-scoped feature flags beyond the current `scope=tenant` limits baseline.
