#!/usr/bin/env bash
set -euo pipefail

DOMAIN=${DOMAIN:-${1:-}}
API_HOST=${API_HOST:-${DOMAIN:+api.${DOMAIN}}}
FRONTEND_HOST=${FRONTEND_HOST:-${DOMAIN:+app.${DOMAIN}}}
API_URL=${API_URL:-${API_HOST:+https://${API_HOST}}}
FRONTEND_URL=${FRONTEND_URL:-${FRONTEND_HOST:+https://${FRONTEND_HOST}}}
ADMIN_EMAIL=${ADMIN_EMAIL:-}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-}

if [ -z "${API_URL}" ]; then
  echo "Usage: DOMAIN=example.com scripts/uptime_check.sh" >&2
  exit 1
fi

curl_opts=("-fsSL" "--max-time" "10")

check() {
  local label=$1 url=$2
  shift 2
  echo "[uptime] checking ${label}: ${url}" >&2
  curl "${curl_opts[@]}" "$@" "${url}" >/dev/null
}

# Health first
check "health" "${API_URL}/health"

token=""
if [ -n "${ADMIN_EMAIL}" ] && [ -n "${ADMIN_PASSWORD}" ]; then
  echo "[uptime] logging in as admin" >&2
  login_body=$(curl "${curl_opts[@]}" -X POST "${API_URL}/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\"}")
  token=$(LOGIN_BODY="$login_body" python - <<'PY'
import json, os
payload = json.loads(os.environ.get("LOGIN_BODY", "{}"))
print(payload.get("access_token", ""))
PY
)
fi

if [ -n "${token}" ]; then
  auth_header=("-H" "Authorization: Bearer ${token}")
  check "metrics" "${API_URL}/metrics" "${auth_header[@]}"
  check "auth/me" "${API_URL}/auth/me" "${auth_header[@]}"
  check "ops/state" "${API_URL}/ops/state" "${auth_header[@]}"
  check "admin/users" "${API_URL}/admin/users" "${auth_header[@]}"
else
  check "metrics" "${API_URL}/metrics"
fi

if [ -n "${FRONTEND_URL}" ]; then
  check "frontend" "${FRONTEND_URL}"
fi

echo "[uptime] all checks passed"
