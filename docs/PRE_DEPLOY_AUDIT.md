# Pre-Deploy Audit Checklist

Use this checklist to confirm the Lunia/Aladdin stack is ready for VPS deployment (deployment itself is out of scope here).

## Repository inventory
- Backend: `lunia_core/app/services` (Flask API, RBAC/JWT/auth/users/flags/limits/audit, telemetry feeds, branding/tenant)
- Frontend: `frontend/` (Vite/React/TS panels for User/Trader/Fund/Admin)
- Infra: `lunia_core/infra/` (compose base + prod overlay, Traefik, monitoring profile)
- Scripts: `scripts/` (guards, smoke, offline verify, wheelhouse, backup/restore, deploy, compose lint)
- Tests: `tests/` (RBAC/auth + tenant + panel wiring contract suites) and `lunia_core/tests` (risk/spot/health)
- Docs: `docs/` (API contract, runbooks, offline install, monitoring, restore drills, UI wiring map)

## Environment variables (baseline)
Populate `lunia_core/.env` (copy from `.env.example`) with at least:
- `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `AUTH_SECRET`, `AUTH_TOKEN_TTL_SECONDS`
- `DATABASE_URL`, `DB_MODE`, `REDIS_URL`
- `DEFAULT_TENANT_SLUG`, `BRAND_NAME`, `BRAND_SUPPORT_EMAIL`
- `AUTH_REQUIRED_FOR_TELEMETRY`, `CORS_ALLOW_ORIGINS`
- Optional: `RABBITMQ_URL`, `DOMAIN`, `ACME_EMAIL` (for prod overlay)

## Verification commands
Local/online path:
```bash
make venv
make install-backend
make rc-verify          # runs guard → preflight → compileall → no placeholders/dead-controls → compose lint → pytest → local smoke
```

Offline/air-gapped path (wheelhouse prepared elsewhere):
```bash
make wheelhouse              # on a connected host
cp -r wheelhouse/ <target>   # move to offline host
make venv
make install-backend-offline
OFFLINE_CI=1 make rc-verify  # delegates to offline-verify; uses wheelhouse-only when present, otherwise skips with guidance
```

## Green conditions before deploy
- Python guard 3.12 ✅
- Preflight checks ✅
- `compileall` on `lunia_core/app/services` ✅
- No placeholders / no-dead-controls scans ✅
- Compose lint ✅ (PyYAML available via wheelhouse or installed; skips only when OFFLINE_CI=1/explicitly disabled)
- RBAC/auth/tenant/panel-wiring tests ✅
- UI wiring map present (`docs/UI_WIRING_MAP.md`) and no-dead-controls gate ✅
- Local smoke ✅ (auth + key ops/telemetry)
- Wheelhouse present for offline installs ✅
- Docs/runbooks up to date (API_CONTRACT, VPS_RUNBOOK, OFFLINE_INSTALL, RESTORE_DRILL, PROD_VALIDATION) ✅
