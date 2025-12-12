# Production Validation and Soak Checklist

Use this checklist immediately after a VPS deployment and during soak windows.

## Post-deploy validation (within 10 minutes)
1. Environment ready and secrets in place:
   ```bash
   ls lunia_core/.env && grep -E 'DOMAIN|ACME_EMAIL' lunia_core/.env
   ```
2. Compose status:
   ```bash
   docker compose -f lunia_core/infra/docker-compose.yml -f lunia_core/infra/docker-compose.prod.yml --env-file lunia_core/.env ps
   ```
3. Run smoke tests (auth + critical reads):
   ```bash
   make smoke
   ```
4. Local dry-run without Docker (launches Flask API on localhost and replays smoke checks):
   ```bash
   make local-smoke
   ```
5. Health and metrics (HTTPS):
   ```bash
   curl -f https://api.${DOMAIN}/health
   curl -k -f https://api.${DOMAIN}/metrics # requires AUTH if enabled
   ```
6. Frontend reachability:
   ```bash
   curl -I https://app.${DOMAIN}
   ```
6. Monitoring targets (when profile enabled):
   - Grafana: https://app.${DOMAIN}:3000 (if published)
   - Prometheus: https://app.${DOMAIN}:9090 (if published)
   - Check Prometheus targets: API, Traefik, node-exporter

## Soak plan (6h / 24h)
- Restarts: `docker compose ... ps` shows `0 (healthy)` for api/traefik/frontend.
- Memory/CPU: observe in Grafana (container memory, CPU usage) or `docker stats`.
- Errors: Prometheus panels/Grafana dashboard — 5xx rate near zero; p95 latency stable.
- Disk: ensure volumes (data/logs/traefik) have >20% free.
- Authentication: repeated login/logout succeeds; audit entries appear.
- Telemetry: `/metrics` scrape OK, Prometheus targets up, Traefik ACME renewals logged.

## Extended checks (weekly/after upgrades)
- Backup round-trip: `make backup` then `make restore BACKUP=...` in staging.
- Load test: `make load-test BASE_URL=https://api.${DOMAIN}` (read-only endpoints).
- Uptime probe: schedule `scripts/uptime_check.sh DOMAIN=${DOMAIN}` via cron/systemd timer.
