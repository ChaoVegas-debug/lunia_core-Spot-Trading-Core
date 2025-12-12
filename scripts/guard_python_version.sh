#!/usr/bin/env bash
set -euo pipefail

# Allow overriding the guard when running in constrained environments
if [[ "${ALLOW_PYTHON_VERSION_OVERRIDE:-0}" == "1" ]]; then
  echo "⚠️ Python version guard overridden (ALLOW_PYTHON_VERSION_OVERRIDE=1)."
  exit 0
fi

REQ="${1:-3.12}"
CUR=$(python -c "import sys;print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if [[ "$CUR" != "$REQ" ]]; then
  echo "❌ Python $CUR detected — requires $REQ.x"
  exit 1
fi

echo "✅ Python $CUR OK"
