#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${SMOKE_ENV_FILE:-$ROOT_DIR/lunia_core/.env}"
SMOKE_INSECURE="${SMOKE_INSECURE:-0}"
SKIP_FRONTEND="${SMOKE_SKIP_FRONTEND:-0}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Env file not found: $ENV_FILE" >&2
  exit 1
fi

set -o allexport
# shellcheck disable=SC1090
source "$ENV_FILE"
set +o allexport

DOMAIN=${DOMAIN:-localhost}
API_BASE=${SMOKE_API_BASE:-"https://api.${DOMAIN}"}
APP_BASE=${SMOKE_APP_BASE:-"https://app.${DOMAIN}"}
AUTH_REQUIRED_FOR_TELEMETRY=${AUTH_REQUIRED_FOR_TELEMETRY:-0}

CURL_OPTS=(-fsSL --retry 2 --connect-timeout 5 --max-time 20)
if [ "$SMOKE_INSECURE" = "1" ]; then
  CURL_OPTS+=(-k)
fi

say() { printf "[smoke] %s\n" "$*"; }

curl_json() {
  local url=$1
  shift
  curl "${CURL_OPTS[@]}" -H "Accept: application/json" "$@" "$url"
}

say "API health check at $API_BASE/health"
curl "${CURL_OPTS[@]}" "$API_BASE/health" >/dev/null

if [ -z "${ADMIN_EMAIL:-}" ] || [ -z "${ADMIN_PASSWORD:-}" ]; then
  echo "ADMIN_EMAIL or ADMIN_PASSWORD not set in env; cannot run auth checks" >&2
  exit 1
fi

say "Logging in as admin"
LOGIN_PAYLOAD=$(cat <<JSON
{"email":"${ADMIN_EMAIL}","password":"${ADMIN_PASSWORD}"}
JSON
)
LOGIN_RESPONSE=$(curl_json "$API_BASE/auth/login" -H "Content-Type: application/json" -X POST -d "$LOGIN_PAYLOAD")
ACCESS_TOKEN=$(python - <<'PY'
import json, sys
resp=json.loads(sys.argv[1])
print(resp.get('access_token',''))
PY
"$LOGIN_RESPONSE")
if [ -z "$ACCESS_TOKEN" ]; then
  echo "Failed to parse access token from /auth/login" >&2
  exit 1
fi
AUTH_HEADER=("-H" "Authorization: Bearer $ACCESS_TOKEN")

say "Verifying /auth/me"
curl_json "$API_BASE/auth/me" "${AUTH_HEADER[@]}" >/dev/null

say "Checking /ops/state"
OPS_HEADERS=()
case "${AUTH_REQUIRED_FOR_TELEMETRY,,}" in
 1|true|yes)
  OPS_HEADERS=("${AUTH_HEADER[@]}")
  ;;
esac
curl_json "$API_BASE/ops/state" "${OPS_HEADERS[@]}" >/dev/null

say "Listing admin users"
curl_json "$API_BASE/admin/users" "${AUTH_HEADER[@]}" >/dev/null

say "Reading audit trail"
curl_json "$API_BASE/admin/audit" "${AUTH_HEADER[@]}" >/dev/null

if [ "$SKIP_FRONTEND" != "1" ]; then
  say "Checking frontend at $APP_BASE"
  curl "${CURL_OPTS[@]}" -I "$APP_BASE" >/dev/null
fi

say "Smoke suite completed successfully"
