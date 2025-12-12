# Lunia / Aladdin Core

Stabilized core for Lunia/Aladdin: spot/futures exchange clients (mock + Binance testnet),
risk manager, capital allocator, AI supervisor + signals, scheduler/guard, Flask API,
arbitrage worker, and optional Telegram facade.

## Requirements

* Python 3.12
* Base dependencies from `requirements/base.txt` (Telegram-free)
* Optional Telegram stack lives in `requirements/telegram.txt` and is not installed by default

## Repository layout (key paths)

```
lunia_core/
  app/
    boot.py
    core/              # exchange clients, risk manager, allocator, portfolio, scheduler
    services/          # API (flask_app.py), scheduler, arbitrage, Telegram facade, reports
    compat/            # lightweight shims for requests/dotenv/prom
    backtester/        # synthetic feed + simple engine
  runtime/             # runtime guard + scheduler harness
  infra/
    docker-compose.yml
    docker-compose.prod.yml
    caddy/Caddyfile
    monitoring/prometheus.yml   # Prometheus scrape targets; Grafana provisioning + starter dashboard included
    ci/github-actions.yml
    systemd/*.service
    logrotate/lunia
  requirements/        # base profiles + optional telegram/all bundles
  tests/               # core functional tests (risk, spot mock, allocators, API, etc.)
  Dockerfile
  main.py              # runtime scheduler/guard entrypoint
```

## Installation

```bash
cd lunia_core
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements/base.txt
cp .env.example .env  # adjust credentials and feature flags
python scripts/init_db.py  # creates SQLite DB, seeds admin if ADMIN_EMAIL/ADMIN_PASSWORD set
```

Network-restricted installs:
- Set `PIP_INDEX_URL` / `PIP_EXTRA_INDEX_URL` / `PIP_TRUSTED_HOST` when behind a proxy (along with `HTTPS_PROXY/HTTP_PROXY/NO_PROXY`).
- Optional offline prep: `bash scripts/build_wheelhouse.sh requirements/base.txt` then build the image with `--build-arg WHEELHOUSE=1` or install locally with `pip install --no-index --find-links=wheelhouse -r requirements/base.txt`.

To enable Telegram later, install `requirements/telegram.txt` in addition to the base profile.

## Running locally

* **API**: `python -m flask --app app.services.api.flask_app run --host=0.0.0.0 --port=8080`
* **Scheduler (rebalance/digest loops)**: `python -m app.services.scheduler.worker`
* **Arbitrage worker**: `python -m app.services.arbitrage.worker`
* **Runtime guard + heartbeat harness**: `python -m lunia_core.main --dry-run` (use `--ticks` to limit)

Redis is optional; set `ENABLE_REDIS=true` and `REDIS_URL` in `.env` when available.

`AUTH_REQUIRED_FOR_TELEMETRY` defaults to `0` so Prometheus can scrape `/metrics`; set it to `1` to require JWT or `X-Admin-Token`.

SQLite is stored at `data/lunia.db` by default (configurable via `DATABASE_URL`);
compose mounts `../data` to persist RBAC/audit state across services.

## Docker Compose (dev/default)

```bash
cd lunia_core/infra
docker compose up -d --build           # api + scheduler + arbitrage + redis
# optional profiles
# docker compose --profile bot up -d    # enable Telegram bot (requires TELEGRAM_BOT_TOKEN in .env)
# docker compose --profile monitoring up -d  # Prometheus + Grafana + node-exporter
# docker compose --profile tls up -d    # legacy Caddy reverse proxy for TLS
# frontend static server
docker compose up -d --build frontend   # React panels on :5173 pointing to api:8080
```
Prometheus config is included; Grafana is pre-provisioned with a Prometheus datasource and a starter dashboard under `infra/monitoring/grafana/provisioning`.

## Production compose + Traefik

A production override lives at `infra/docker-compose.prod.yml` and introduces Traefik with HTTPS
and HSTS. Services are set to `restart: unless-stopped`, health-checked, and log-limited.

**Prep**

```bash
cp lunia_core/.env.example lunia_core/.env
bash scripts/gen_secrets.sh  # fills AUTH_SECRET and ADMIN_PASSWORD if defaults are present
# Set DOMAIN, ACME_EMAIL, CORS_ALLOW_ORIGINS, DATABASE_URL, AUTH_SECRET, ADMIN_EMAIL/ADMIN_PASSWORD
```

**Deploy on VPS (Ubuntu 24.04)**

```bash
bash scripts/deploy_vps.sh
# or
make deploy
```

The deploy script is idempotent, creates data/log directories, builds/pulls images with the prod
override, and waits for `/health` to report ready. Traefik will obtain certificates for
`app.$DOMAIN` and `api.$DOMAIN` using HTTP-01.

End-to-end VPS steps, DNS/TLS prerequisites, and smoke checks live in `docs/VPS_RUNBOOK.md`.

Backups/restores: use `make backup` (archives DB/logs/env/ACME) and follow `docs/RESTORE_DRILL.md` to practice restores. `scripts/uptime_check.sh` provides a lightweight HTTPS probe suitable for cron/systemd timers.

Health checks and status:

```bash
docker compose -f lunia_core/infra/docker-compose.yml -f lunia_core/infra/docker-compose.prod.yml --env-file lunia_core/.env ps
# API health from within the container
docker compose -f ... --env-file lunia_core/.env exec api python - <<'PY'
import urllib.request; urllib.request.urlopen('http://localhost:8080/health', timeout=5)
PY
```

## Logging & rotation

Compose services use json-file logging with rotation (`max-size=10m`, `max-file=3`). A logrotate
example remains under `infra/logrotate/`; apply it system-wide if desired.

## Testing

Base checks used in CI (Python 3.12):

```bash
python scripts/preflight.py
bash scripts/ensure-no-telegram.sh
python scripts/health/all_checks.py
pytest -q tests/test_health_scripts.py tests/test_runtime_guard.py tests/test_api_schemas.py \
  lunia_core/tests/test_risk.py lunia_core/tests/test_spot_mock.py
```

Telegram surface test (optional profile): `pytest -q tests/test_telegram_optional.py`

Domain-based production smoke (requires DNS/TLS + admin creds in `.env`): `make smoke`
