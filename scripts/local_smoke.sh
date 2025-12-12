#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${LOCAL_SMOKE_ENV:-$ROOT_DIR/lunia_core/.env}"
if [ ! -f "$ENV_FILE" ] && [ -f "$ROOT_DIR/lunia_core/.env.example" ]; then
  echo "[local-smoke] Falling back to $ROOT_DIR/lunia_core/.env.example" >&2
  ENV_FILE="$ROOT_DIR/lunia_core/.env.example"
fi
PORT="${LOCAL_SMOKE_PORT:-18080}"
HOST="127.0.0.1"

if [ ! -f "$ENV_FILE" ]; then
  echo "Env file not found: $ENV_FILE" >&2
  exit 1
fi

set -o allexport
# shellcheck disable=SC1090
source "$ENV_FILE"
set +o allexport

if [ -z "${ADMIN_EMAIL:-}" ] || [ -z "${ADMIN_PASSWORD:-}" ]; then
  echo "ADMIN_EMAIL/ADMIN_PASSWORD must be set in $ENV_FILE" >&2
  exit 1
fi

export HOST
export PORT
export AUTH_REQUIRED_FOR_TELEMETRY=${AUTH_REQUIRED_FOR_TELEMETRY:-1}

say() { printf "[local-smoke] %s\n" "$*"; }

cleanup() {
  if [ -n "${API_PID:-}" ] && kill -0 "$API_PID" 2>/dev/null; then
    kill "$API_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

say "Starting API locally on ${HOST}:${PORT}"
PYTHONPATH="$ROOT_DIR" python -m lunia_core.app.services.api.flask_app >/tmp/lunia_local_api.log 2>&1 &
API_PID=$!

for i in {1..20}; do
  if curl -fsS "http://${HOST}:${PORT}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
  if [ "$i" -eq 20 ]; then
    echo "API failed to start; check /tmp/lunia_local_api.log" >&2
    exit 1
  fi
done

say "API is up; running smoke calls"
LOGIN_PAYLOAD=$(cat <<JSON
{"email":"${ADMIN_EMAIL}","password":"${ADMIN_PASSWORD}"}
JSON
)
TOKEN=$(curl -fsS -H "Content-Type: application/json" -d "$LOGIN_PAYLOAD" "http://${HOST}:${PORT}/auth/login" | python - <<'PY'
import json,sys
resp=json.loads(sys.stdin.read())
print(resp.get('access_token',''))
PY
)
if [ -z "$TOKEN" ]; then
  echo "Failed to obtain token" >&2
  exit 1
fi
AUTH_HEADER=("-H" "Authorization: Bearer $TOKEN")

curl -fsS "http://${HOST}:${PORT}/auth/me" "${AUTH_HEADER[@]}" >/dev/null
curl -fsS "http://${HOST}:${PORT}/ops/state" "${AUTH_HEADER[@]}" >/dev/null
curl -fsS "http://${HOST}:${PORT}/portfolio/snapshot" "${AUTH_HEADER[@]}" >/dev/null
curl -fsS "http://${HOST}:${PORT}/ai/signals" "${AUTH_HEADER[@]}" >/dev/null
curl -fsS "http://${HOST}:${PORT}/admin/audit" "${AUTH_HEADER[@]}" >/dev/null

say "Local smoke complete"
