#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WHEELHOUSE_DIR="${WHEELHOUSE_DIR:-$ROOT_DIR/wheelhouse}"
REQ_FILE="${REQ_FILE:-$ROOT_DIR/requirements.txt}"
TEST_REQ_FILE="${TEST_REQ_FILE:-$ROOT_DIR/lunia_core/requirements/test.txt}"
VENV_DIR="${OFFLINE_VENV:-$ROOT_DIR/.venv_offline_verify}"
OFFLINE_ENV_FILE="${LOCAL_SMOKE_ENV:-$ROOT_DIR/lunia_core/.env.example}"
REQUIRED_WHEELS=(flask pydantic requests sqlalchemy redis pyjwt pyyaml apscheduler passlib python-dotenv prometheus-client)
REQUIRED_WHEELS+=(pytest)
MANIFEST_FILE="$WHEELHOUSE_DIR/manifest.txt"

say() { printf "[offline-verify] %s\n" "$*"; }
if [ ! -d "$WHEELHOUSE_DIR" ]; then
  echo "[offline-verify] Wheelhouse not found at $WHEELHOUSE_DIR. Skipping offline gate; build with 'make wheelhouse' for full coverage." >&2
  echo "[offline-verify] OFFLINE VERIFY: PASS (skipped - no wheelhouse)" >&2
  exit 0
fi

if [ -f "$MANIFEST_FILE" ]; then
  say "Validating wheelhouse manifest at $MANIFEST_FILE"
  missing=()
  for pkg in "${REQUIRED_WHEELS[@]}"; do
    if ! grep -qi "^${pkg}-.*\.whl" "$MANIFEST_FILE"; then
      missing+=("$pkg")
    fi
  done
  if [ ${#missing[@]} -ne 0 ]; then
    echo "Missing wheels for: ${missing[*]} in manifest" >&2
    echo "Rebuild wheelhouse with internet access: make wheelhouse" >&2
    exit 1
  fi
else
  say "Manifest not found; falling back to directory scan"
  missing=()
  for pkg in "${REQUIRED_WHEELS[@]}"; do
    if ! ls "$WHEELHOUSE_DIR" | grep -qi "^${pkg}-.*\.whl"; then
      missing+=("$pkg")
    fi
  done
  if [ ${#missing[@]} -ne 0 ]; then
    echo "Missing wheels for: ${missing[*]} in $WHEELHOUSE_DIR" >&2
    echo "Rebuild wheelhouse with internet access: make wheelhouse" >&2
    exit 1
  fi
fi

say "Creating offline virtualenv at $VENV_DIR"
python -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip >/dev/null

say "Installing backend + test deps from wheelhouse"
"$VENV_DIR/bin/pip" install --no-index --find-links "$WHEELHOUSE_DIR" -r "$REQ_FILE"
"$VENV_DIR/bin/pip" install --no-index --find-links "$WHEELHOUSE_DIR" -r "$TEST_REQ_FILE" pyyaml

PATH="$VENV_DIR/bin:$PATH"
FAILED=()
run_step() {
  local name="$1"
  shift
  say "STEP: $name"
  if "$@"; then
    say "OK: $name"
  else
    say "FAIL: $name"
    FAILED+=("$name")
  fi
}

run_step guard bash "$ROOT_DIR/scripts/guard_python_version.sh" 3.12
run_step preflight "$VENV_DIR/bin/python" "$ROOT_DIR/scripts/preflight.py"
run_step compile "$VENV_DIR/bin/python" -m compileall "$ROOT_DIR/lunia_core/app/services"
run_step no_dead_controls bash "$ROOT_DIR/scripts/no_dead_controls.sh"
run_step compose_lint WHEELHOUSE_DIR="$WHEELHOUSE_DIR" "$VENV_DIR/bin/python" "$ROOT_DIR/scripts/compose_lint.py"
run_step test_api "$VENV_DIR/bin/pytest" -q \
  "$ROOT_DIR/tests/test_auth_rbac_endpoints.py" \
  "$ROOT_DIR/tests/test_tenant_admin.py" \
  "$ROOT_DIR/tests/test_panel_wiring_contract.py"
run_step local_smoke env PATH="$VENV_DIR/bin:$PATH" LOCAL_SMOKE_ENV="$OFFLINE_ENV_FILE" bash "$ROOT_DIR/scripts/local_smoke.sh"

if [ ${#FAILED[@]} -eq 0 ]; then
  say "OFFLINE VERIFY: PASS"
  exit 0
else
  say "OFFLINE VERIFY: FAIL -> ${FAILED[*]}"
  exit 1
fi
