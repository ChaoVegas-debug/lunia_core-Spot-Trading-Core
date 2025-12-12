#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_BASE="$ROOT_DIR/lunia_core/infra/docker-compose.yml"
COMPOSE_PROD="$ROOT_DIR/lunia_core/infra/docker-compose.prod.yml"
ENV_FILE="$ROOT_DIR/lunia_core/.env"
DATA_DIR="$ROOT_DIR/lunia_core/data"
LOG_DIR="$ROOT_DIR/lunia_core/logs"
TRAEFIK_DIR="$ROOT_DIR/data/traefik"

command -v docker >/dev/null 2>&1 || { echo "docker is required" >&2; exit 1; }

if docker compose version >/dev/null 2>&1; then
  DC=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  DC=(docker-compose)
else
  echo "docker compose plugin or docker-compose binary required" >&2
  exit 1
fi

mkdir -p "$DATA_DIR" "$LOG_DIR" "$TRAEFIK_DIR"

bash "$ROOT_DIR/scripts/gen_secrets.sh"

if [ ! -f "$ENV_FILE" ]; then
  echo "Env file $ENV_FILE missing" >&2
  exit 1
fi

set -o allexport
# shellcheck disable=SC1090
source "$ENV_FILE"
set +o allexport

COMPOSE_ARGS=("-f" "$COMPOSE_BASE" "-f" "$COMPOSE_PROD" "--env-file" "$ENV_FILE")

"${DC[@]}" "${COMPOSE_ARGS[@]}" pull
"${DC[@]}" "${COMPOSE_ARGS[@]}" build
"${DC[@]}" "${COMPOSE_ARGS[@]}" up -d

for attempt in {1..10}; do
  if "${DC[@]}" "${COMPOSE_ARGS[@]}" exec -T api python - <<'PY' >/dev/null 2>&1; then
import urllib.request
urllib.request.urlopen('http://localhost:8080/health', timeout=5)
print('ok')
PY
    echo "API healthy"
    break
  fi
  echo "Waiting for API health (${attempt}/10)" && sleep 5
  if [ "$attempt" -eq 10 ]; then
    echo "API did not become healthy" >&2
    exit 1
  fi
done

"${DC[@]}" "${COMPOSE_ARGS[@]}" ps

DOMAIN=${DOMAIN:-example.com}
echo "Frontend: https://app.${DOMAIN}"
echo "API:      https://api.${DOMAIN}"

if [ "${RUN_SMOKE:-0}" = "1" ]; then
  echo "Running smoke tests via scripts/smoke_test.sh"
  SMOKE_ENV_FILE="$ENV_FILE" SMOKE_INSECURE="${SMOKE_INSECURE:-0}" bash "$ROOT_DIR/scripts/smoke_test.sh"
fi
