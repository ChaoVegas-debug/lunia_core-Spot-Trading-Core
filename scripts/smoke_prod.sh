#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE="docker compose --project-directory $ROOT_DIR -f $ROOT_DIR/docker-compose.prod.yml"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  Integration Gate I.4 — Production Smoke Test Pack        ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo
echo "[INFO] Checking if services are running..."

if ! $COMPOSE ps --format json | grep -q '"State":"running"'; then
  echo "[FAIL] No services appear to be running"
  echo
  echo "Start services with:"
  echo "  docker compose -f docker-compose.prod.yml up -d"
  exit 1
fi

echo "[OK] Services are running"
echo

echo "[INFO] Checking backend health endpoint..."
if ! curl -fsS http://localhost:8000/api/health >/dev/null; then
  echo "[FAIL] Backend health endpoint not responding"
  exit 1
fi
echo "[OK] Backend health endpoint responding"
echo

echo "[INFO] Smoke test PASSED"
exit 0
