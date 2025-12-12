#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_TEMPLATE="$ROOT_DIR/lunia_core/.env.example"
ENV_FILE="$ROOT_DIR/lunia_core/.env"

generate_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  else
    python - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
  fi
}

generate_password() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -base64 24 | tr -d '\n'
  else
    python - <<'PY'
import secrets,string
alphabet = string.ascii_letters + string.digits + "!@#%^&*()-_=+"
print(''.join(secrets.choice(alphabet) for _ in range(24)))
PY
  fi
}

update_kv() {
  local key="$1" value="$2"
  if grep -q "^${key}=" "$ENV_FILE"; then
    perl -0777 -pi -e "s/^${key}=.*$/${key}=${value}/m" "$ENV_FILE"
  else
    echo "${key}=${value}" >> "$ENV_FILE"
  fi
}

if [ ! -f "$ENV_TEMPLATE" ]; then
  echo "Template $ENV_TEMPLATE missing" >&2
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  cp "$ENV_TEMPLATE" "$ENV_FILE"
  echo "Created $ENV_FILE from template"
fi

umask 077

current_secret="$(grep -E '^AUTH_SECRET=' "$ENV_FILE" | cut -d'=' -f2- || true)"
if [ -z "$current_secret" ] || [[ "$current_secret" == "change-me" ]]; then
  update_kv "AUTH_SECRET" "$(generate_secret)"
  echo "Updated AUTH_SECRET"
fi

current_password="$(grep -E '^ADMIN_PASSWORD=' "$ENV_FILE" | cut -d'=' -f2- || true)"
if [ -z "$current_password" ] || [[ "$current_password" == "admin123" ]]; then
  update_kv "ADMIN_PASSWORD" "$(generate_password)"
  echo "Updated ADMIN_PASSWORD"
fi

if [ ! -s "$ENV_FILE" ]; then
  echo "Env file is empty; aborting" >&2
  exit 1
fi

chmod 600 "$ENV_FILE"
echo "Env bootstrap complete at $ENV_FILE"
