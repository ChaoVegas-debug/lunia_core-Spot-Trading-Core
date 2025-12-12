# Lunia Core + Spot Trading Bootstrap

Stabilized snapshot of the Lunia/Aladdin trading core with RBAC/JWT auth, cockpit UI, and
production-ready Docker stacks.

- Python 3.12 baseline
- Base profile installs only production-safe dependencies (Telegram is optional)
- Frontend: Vite/React/TypeScript panels (User/Trader/Fund/Admin) aligned to `docs/API_CONTRACT.md`
- Backend docs, CI matrix, and Docker profiles live under `lunia_core/README.md`
- Frontend registry/proxy guidance lives under `frontend/README.md`
- Production runbook, smoke suite, restore drills, offline install, and monitoring are documented in `docs/`

## 100% readiness gates (no-deploy)

- Offline backend install path: `make wheelhouse` → copy `wheelhouse/` → `make venv` → `make install-backend-offline`
- Deterministic verification (offline): `make offline-verify` or `OFFLINE_CI=1 make rc-verify` (uses `.venv_offline_verify`, installs from wheelhouse, runs compose lint + RBAC tests + local smoke)
- Release candidate gate (online): `make venv && make install-backend && make rc-verify` (guard → preflight → compileall → placeholder + dead-control scans → compose lint → pytest → local smoke)
- Placeholder gates: `make no-placeholders` and `make no-dead-controls` (fails on TODO/placeholder markers or stub handlers outside allowlists)
- Compose lint: `make compose-lint` (requires PyYAML; offline: `make install-backend-offline` first)
- Load probe: `make load-test BASE_URL=http://localhost:8080`
- Offline guide: see `docs/OFFLINE_INSTALL.md` for wheelhouse build/transfer and npm alternatives
- Pre-deploy audit: see `docs/PRE_DEPLOY_AUDIT.md` for the full checklist

## Production Deploy on VPS (Ubuntu 24.04)

Requirements: Docker + Docker Compose plugin, DNS A records for `app.<DOMAIN>` and `api.<DOMAIN>`
pointing at the VPS, and open ports 80/443.

1. Copy and customize env: `cp lunia_core/.env.example lunia_core/.env` (or run `bash scripts/gen_secrets.sh`).
   Set `DOMAIN`, `ACME_EMAIL`, `AUTH_SECRET`, `ADMIN_EMAIL/ADMIN_PASSWORD`, `DATABASE_URL`, `AUTH_TOKEN_TTL_SECONDS`,
   and CORS origins for your domains.
2. Optional: adjust feature flags/limits via `.env` before first boot; SQLite will live in `lunia_core/data/`.
3. Deploy: `bash scripts/deploy_vps.sh` (idempotent) or `make deploy`.
4. Verify:
   - `docker compose -f lunia_core/infra/docker-compose.yml -f lunia_core/infra/docker-compose.prod.yml --env-file lunia_core/.env ps`
   - API health: `docker compose ... exec api python - <<'PY'
import urllib.request; urllib.request.urlopen('http://localhost:8080/health', timeout=5)
PY`
   - Frontend: browse `https://app.<DOMAIN>`; API: `https://api.<DOMAIN>/health`
5. (Optional) Enable monitoring profile: `docker compose -f lunia_core/infra/docker-compose.yml -f lunia_core/infra/docker-compose.prod.yml --env-file lunia_core/.env --profile monitoring up -d`

See `docs/VPS_RUNBOOK.md` for end-to-end DNS/TLS prerequisites, commands, smoke tests, and troubleshooting.

Troubleshooting:
- ACME/Traefik: ensure ports 80/443 are reachable and `DOMAIN`/`ACME_EMAIL` are set; check `traefik` service logs.
- Registry/proxy: set `PIP_INDEX_URL`/`PIP_EXTRA_INDEX_URL`/`PIP_TRUSTED_HOST` for Python and `NPM_CONFIG_REGISTRY`/`HTTPS_PROXY`/`HTTP_PROXY`/`NO_PROXY` before installs if behind a proxy.
- Offline build: prepare wheels via `scripts/build_wheelhouse.sh` and build the API image with `--build-arg WHEELHOUSE=1` to avoid live index calls.
- Permissions: `chmod 600 lunia_core/.env`; keep `data/traefik/acme.json` intact to preserve certificates.
- Backups: `make backup` (archives DB/logs/env/ACME) and follow `docs/RESTORE_DRILL.md` for restore validation.
- Uptime/alerts: schedule `DOMAIN=<domain> bash scripts/uptime_check.sh` or `make uptime` via cron/systemd; full smoke via `make smoke`.

One-liners for owners:
```bash
make wheelhouse                      # build offline wheels
make install-backend-offline         # install backend deps from wheelhouse only (uses .venv)
make offline-verify                  # offline venv install + compose lint + RBAC tests + local smoke
make install-backend && make rc-verify    # install deps into .venv and run full release-candidate gate
make no-placeholders                 # ensure no TODO/placeholder strings in API/frontend
make no-dead-controls                # ensure no stub/disabled UI actions remain
make local-smoke                     # bring up local API and verify key endpoints
```

## Local workflows

- Backend quickstart: see `lunia_core/README.md` (`python scripts/preflight.py`, `python -m flask --app app.services.api.flask_app run`).
- Frontend quickstart: `cd frontend && cp .env.example .env && npm ci && npm run dev`.
- CI skips frontend build when `SKIP_FRONTEND_CI=1` or `SKIP_FRONTEND_BUILD=1` is set (for registry-blocked environments).

## Make targets

```
make up       # bring up api/scheduler/arbitrage/frontend via compose (prod overlays included)
make down     # stop stack
make logs     # tail logs
make ps       # service status
make build    # build images
make deploy   # idempotent VPS deploy wrapper
make verify   # guard + preflight + health checks
make rc-verify # guard + preflight + compileall + placeholders + compose lint + pytest + local smoke (OFFLINE_CI=1 for wheelhouse path)
make smoke    # domain-based HTTPS smoke across API/auth/admin/frontend
make local-smoke # start local Flask API + run smoke checks without docker
make test-api # pytest RBAC/auth/branding contract tests
make wheelhouse # download wheels + freeze snapshot for offline install
make install-backend-offline # install backend from local wheelhouse only
make offline-verify # install from wheelhouse, run contract tests + local smoke
make no-placeholders # fail on TODO/placeholder markers outside allowlist
make no-dead-controls # fail on stub/disabled UI controls
make backup   # archive data/logs/env/ACME with 14-day retention by default
make restore BACKUP=<path>   # restore from an archive
make uptime   # curl-based uptime probe against api.<DOMAIN> and app.<DOMAIN>
```
