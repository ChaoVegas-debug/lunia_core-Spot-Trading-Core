#!/usr/bin/env bash
set -euo pipefail

if ! command -v rg >/dev/null 2>&1; then
  echo "ripgrep (rg) is required for dead control scanning" >&2
  exit 1
fi

EXCLUDES="--glob=!node_modules --glob=!frontend/node_modules --glob=!.git --glob=!*.pyc --glob=!__pycache__ --glob=!.venv"
PATTERN='DEAD_CONTROL|DEAD-CONTROL'

if rg --hidden $EXCLUDES "$PATTERN" >/dev/null 2>&1; then
  echo "Dead control markers detected; please clean up stub UI controls." >&2
  rg --hidden $EXCLUDES "$PATTERN"
  exit 1
fi

echo "No dead control markers detected."
