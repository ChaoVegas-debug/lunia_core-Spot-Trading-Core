#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON:-python}" 
LOG_DIR="${ROOT_DIR}/logs"
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/runtime.log"

export OFFLINE_CI="${OFFLINE_CI:-0}"

child_pid=""
trap 'echo "[runtime] termination requested"; if [ -n "${child_pid:-}" ]; then kill -TERM "${child_pid}" 2>/dev/null || true; fi' INT TERM

echo "[runtime] starting Lunia Core (OFFLINE_CI=${OFFLINE_CI})"
"${PYTHON_BIN}" -m lunia_core.main "$@" >>"${LOG_FILE}" 2>&1 &
child_pid=$!
wait "${child_pid}"
status=$?
echo "[runtime] exited with status ${status}"
exit "${status}"
