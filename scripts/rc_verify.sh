#!/usr/bin/env bash
set -euo pipefail

PY_CMD=${PY_CMD:-python}
PYTEST_CMD=${PYTEST_CMD:-pytest}
WHEELHOUSE_DIR=${WHEELHOUSE_DIR:-wheelhouse}

bash scripts/guard_python_version.sh

if [ "${OFFLINE_CI:-0}" = "1" ]; then
  echo "Running in offline mode; installing from wheelhouse at ${WHEELHOUSE_DIR}"
  $PY_CMD -m pip install --no-index --find-links "$WHEELHOUSE_DIR" -r requirements.txt -r lunia_core/requirements/test.txt
  $PY_CMD -m pip install --no-index --find-links "$WHEELHOUSE_DIR" pyyaml
fi

echo "Executing release-candidate preflight checks"
$PY_CMD scripts/preflight.py
$PY_CMD scripts/health/all_checks.py

$PYTEST_CMD tests/test_api_schemas.py lunia_core/tests/test_risk.py lunia_core/tests/test_spot_mock.py
