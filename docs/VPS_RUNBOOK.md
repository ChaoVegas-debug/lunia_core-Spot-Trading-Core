# VPS Runbook (Production Deploy)

This guide walks through the first production launch of Lunia/Aladdin on an Ubuntu 24.04 VPS using Docker Compose with Traefik TLS.

## Prerequisites
- Public DNS A records:
  - `app.<DOMAIN>` -> VPS IP
  - `api.<DOMAIN>` -> VPS IP
- Open ports: **80** and **443** to the VPS
- Installed: Docker + Docker Compose plugin (`docker compose version`)
- Cloned repo on the VPS: `git clone https://github.com/.../lunia_core-Spot-Trading-Core.git`
- Tools: `curl`, `tar`, and `python3` available in PATH for smoke/uptime checks

## One-time setup
```bash
cd lunia_core-Spot-Trading-Core
# Generate or copy env (edit DOMAIN/ACME_EMAIL, auth, DB, CORS)
bash scripts/gen_secrets.sh
# or
cp lunia_core/.env.example lunia_core/.env && edit
```

Key env to review:
- `DOMAIN`, `ACME_EMAIL` (Traefik/ACME)
- `AUTH_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`
- `DATABASE_URL` (defaults to SQLite under `lunia_core/data`)
- `CORS_ALLOW_ORIGINS` (e.g., `https://app.<DOMAIN>`)
- Traefik/routing: `LOGIN_RATE_LIMIT_AVG/BURST`, `ADMIN_IP_ALLOWLIST` (set to a CIDR to enable IP gating on API, pair with `ADMIN_IP_MIDDLEWARE=lunia-admin-allow`), `TRAEFIK_LOG_LEVEL`
- Proxy/registry vars when required: `PIP_INDEX_URL`, `PIP_EXTRA_INDEX_URL`, `PIP_TRUSTED_HOST`, `NPM_CONFIG_REGISTRY`, `HTTPS_PROXY/HTTP_PROXY/NO_PROXY`
- Proxy/registry vars when required: `PIP_INDEX_URL`, `PIP_EXTRA_INDEX_URL`, `PIP_TRUSTED_HOST`, `NPM_CONFIG_REGISTRY`, `HTTPS_PROXY/HTTP_PROXY/NO_PROXY`
- Optional offline prep: run `bash scripts/build_wheelhouse.sh requirements/base.txt` on a machine with internet, copy the `wheelhouse/` directory to the VPS, and build the API image with `--build-arg WHEELHOUSE=1`.

## Golden commands (operators)
```bash
make deploy      # build + up with prod overlay
make smoke       # HTTPS health/auth/admin probes
make backup      # archive data/logs/env/traefik acme
make load-test BASE_URL=https://api.${DOMAIN} ARGS="--rps 5 --duration 60"
docker compose -f lunia_core/infra/docker-compose.yml -f lunia_core/infra/docker-compose.prod.yml --env-file lunia_core/.env logs -f traefik api frontend
```

## Deploy
```bash
make deploy   # idempotent wrapper around compose build/up with prod overlay
```

What it does:
- Ensures data/log directories exist
- Builds/pulls images using `infra/docker-compose.yml` + `infra/docker-compose.prod.yml`
- Starts stack with Traefik HTTPS and waits for API health (`/health`)

## Traefik / ACME verification
```bash
# Show Traefik logs (ACME, routing)
docker compose -f lunia_core/infra/docker-compose.yml -f lunia_core/infra/docker-compose.prod.yml --env-file lunia_core/.env logs traefik
```
- Certificates stored on the host under `data/traefik/acme.json` (bind-mounted to Traefik).
- Successful issuance appears as `Server responded with a certificate` in logs.

## Service checks
```bash
# Compose status
docker compose -f lunia_core/infra/docker-compose.yml -f lunia_core/infra/docker-compose.prod.yml --env-file lunia_core/.env ps

# API health (HTTPS via domain)
curl -fsSL https://api.${DOMAIN}/health

# Frontend landing page
curl -I https://app.${DOMAIN}
```

## Smoke suite (automated)
```bash
make smoke    # runs scripts/smoke_test.sh using lunia_core/.env for credentials/domain
```
The suite logs in as the admin user, hits `/auth/me`, `/ops/state`, `/admin/users`, `/admin/audit`, and checks the frontend endpoint.
Flags: `SMOKE_INSECURE=1` to skip TLS verification (self-signed) and `SMOKE_SKIP_FRONTEND=1` to bypass the UI probe.

For lightweight uptime checks (suitable for cron/systemd timers):
```bash
DOMAIN=example.com bash scripts/uptime_check.sh
```

## Troubleshooting
- **ACME fails**: ensure ports 80/443 are reachable and `DOMAIN`/`ACME_EMAIL` are set; retry `make deploy`.
- **Proxy/registry blocks (pip/npm)**: set `PIP_INDEX_URL`/`PIP_EXTRA_INDEX_URL`/`PIP_TRUSTED_HOST` or `NPM_CONFIG_REGISTRY` plus `HTTPS_PROXY/HTTP_PROXY/NO_PROXY` before build/install.
- **Health check fails**: `docker compose ... logs api` and confirm DB/Redis URLs; rerun `make deploy` after fixing env.
- **Certificates not reused**: keep `traefik-acme` volume between deploys.

## Monitoring + Backups
- Enable Prometheus/Grafana/node-exporter with the monitoring profile:
  ```bash
  docker compose -f lunia_core/infra/docker-compose.yml -f lunia_core/infra/docker-compose.prod.yml --env-file lunia_core/.env --profile monitoring up -d
  ```
  Prometheus scrapes API `/metrics`, workers, Traefik, and node-exporter. Grafana is pre-provisioned with a Prometheus datasource and a starter dashboard.
- Run a backup (keeps 14 days by default): `make backup` (archives `lunia_core/data`, `lunia_core/logs`, `.env`, `data/traefik`).
- Restore drill: follow `docs/RESTORE_DRILL.md` and validate with `make smoke`.
