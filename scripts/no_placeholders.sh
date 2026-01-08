#!/usr/bin/env bash
set -euo pipefail

if ! command -v rg >/dev/null 2>&1; then
  echo "ripgrep (rg) is required for placeholder scanning" >&2
  exit 1
fi

EXCLUDES="--glob=!node_modules --glob=!frontend/node_modules --glob=!.git --glob=!*.pyc --glob=!__pycache__ --glob=!.venv"
PATTERN='PLACEHOLDER|TODO_PLACEHOLDER'

if rg --hidden $EXCLUDES "$PATTERN" >/dev/null 2>&1; then
  echo "Placeholder markers detected; please remove remaining TODO/PLACEHOLDER strings." >&2
  rg --hidden $EXCLUDES "$PATTERN"
  exit 1
fi

echo "No placeholder markers detected."
