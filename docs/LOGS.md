# Logging Guide

## Where logs live
- **Docker logs:** `docker compose logs -f <service>` (e.g., `api`, `scheduler`, `arbitrage`, `traefik`).
- **Host volumes:**
  - API and workers: `lunia_core/logs/`
  - Traefik ACME and runtime: `data/traefik/`

## Log rotation
All services use Docker json-file logging with `max-size=10m` and `max-file=3` (see compose files). Rotate host log files with standard tools if they grow beyond expectations.

## Debugging tips
- Enable verbose API logging by setting `LOG_LEVEL=DEBUG` in `.env` before `make deploy`.
- Filter recent operations:
  ```bash
  docker compose -f lunia_core/infra/docker-compose.yml \
    -f lunia_core/infra/docker-compose.prod.yml \
    --env-file lunia_core/.env logs api | tail -n 200
  ```
- Compare UI audit trail with backend `/ops/logs` to correlate control actions.

## Ops logs endpoint vs docker logs
- `/ops/logs` (requires admin token) streams recent application-level events captured by the API service.
- Docker logs include container lifecycle events, dependency errors, and Traefik routing issues.

## Switching log verbosity
- API: `LOG_LEVEL` env var (`INFO` default).
- Traefik: set `TRAEFIK_LOG_LEVEL` in `.env` (defaults to `INFO`).

## Lightweight alerting
- `scripts/uptime_check.sh` performs HTTPS checks against `api.<DOMAIN>`/`app.<DOMAIN>`, logs to stderr, and exits non-zero on failure.
- Example cron entry (every 5 minutes):
  ```cron
  */5 * * * * cd /opt/lunia && DOMAIN=example.com bash scripts/uptime_check.sh >> /var/log/lunia/uptime.log 2>&1
  ```
