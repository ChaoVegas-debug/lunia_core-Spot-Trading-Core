#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY_CMD=${PY_CMD:-python}
OFFLINE=${OFFLINE_CI:-0}
FAILED=()
STEPS=()

run_step() {
  local name="$1"
  shift
  echo "[rc-verify] STEP: $name"
  if "$@"; then
    echo "[rc-verify] OK: $name"
  else
    echo "[rc-verify] FAIL: $name"
    FAILED+=("$name")
  fi
}

if [[ "$OFFLINE" == "1" ]]; then
  echo "[rc-verify] OFFLINE_CI=1 detected; delegating to offline_verify"
  exec bash "$ROOT_DIR/scripts/offline_verify.sh"
fi

check_imports() {
  "$PY_CMD" - <<'PY'
try:
    import flask  # type: ignore
    import sqlalchemy  # type: ignore
    import pytest  # type: ignore
except Exception as exc:
    raise SystemExit(f"Missing runtime/test dependency: {exc}\nRun 'make install-backend' (online) or 'make wheelhouse && OFFLINE_CI=1 make rc-verify' for offline mode")
PY
}

run_step guard "bash" "$ROOT_DIR/scripts/guard_python_version.sh" 3.12
run_step deps check_imports
run_step preflight "$PY_CMD" "$ROOT_DIR/scripts/preflight.py"
run_step compile "$PY_CMD" -m compileall "$ROOT_DIR/lunia_core/app/services"
run_step no_placeholders "bash" "$ROOT_DIR/scripts/no_placeholders.sh"
run_step no_dead_controls "bash" "$ROOT_DIR/scripts/no_dead_controls.sh"
run_step compose_lint WHEELHOUSE_DIR="$WHEELHOUSE_DIR" "$PY_CMD" "$ROOT_DIR/scripts/compose_lint.py"
run_step test_api "$PY_CMD" -m pytest \
  "$ROOT_DIR/tests/test_auth_rbac_endpoints.py" \
  "$ROOT_DIR/tests/test_tenant_admin.py" \
  "$ROOT_DIR/tests/test_panel_wiring_contract.py"
run_step local_smoke "bash" "$ROOT_DIR/scripts/local_smoke.sh"

if [[ ${#FAILED[@]} -eq 0 ]]; then
  echo "RC VERIFY: PASS"
  exit 0
else
  echo "RC VERIFY: FAIL"
  echo "Failed steps: ${FAILED[*]}" >&2
  exit 1
fi
