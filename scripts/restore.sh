#!/usr/bin/env bash
set -euo pipefail

if [ "${1:-}" == "" ]; then
  echo "Usage: scripts/restore.sh <archive-path>" >&2
  exit 1
fi

ARCHIVE="$1"
if [ ! -f "$ARCHIVE" ]; then
  echo "[restore] archive not found: $ARCHIVE" >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

pushd "${REPO_ROOT}" >/dev/null
mkdir -p lunia_core/data lunia_core/logs data/traefik

tar -xzf "$ARCHIVE" -C "${REPO_ROOT}"
echo "[restore] restored from $ARCHIVE"

popd >/dev/null
