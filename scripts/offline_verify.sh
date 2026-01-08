#!/usr/bin/env bash
set -euo pipefail

PY_CMD=${PY_CMD:-python}
PYTEST_CMD=${PYTEST_CMD:-pytest}
WHEELHOUSE_DIR=${WHEELHOUSE_DIR:-wheelhouse}

if [ ! -d "$WHEELHOUSE_DIR" ]; then
  echo "Wheelhouse directory '$WHEELHOUSE_DIR' not found. Build it with 'make wheelhouse' before running offline verification." >&2
  exit 1
fi

echo "Verifying Python version"
bash scripts/guard_python_version.sh

echo "Installing dependencies from local wheelhouse"
$PY_CMD -m pip install --no-index --find-links "$WHEELHOUSE_DIR" -r requirements.txt -r lunia_core/requirements/test.txt
$PY_CMD -m pip install --no-index --find-links "$WHEELHOUSE_DIR" pyyaml

echo "Running offline preflight checks"
$PY_CMD scripts/preflight.py
$PY_CMD -m compileall lunia_core/app/services

echo "Running targeted API contract tests offline"
$PYTEST_CMD tests/test_auth_rbac_endpoints.py tests/test_tenant_admin.py tests/test_panel_wiring_contract.py
