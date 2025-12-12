#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR=${BACKUP_DIR:-"${REPO_ROOT}/backups"}
RETENTION_DAYS=${RETENTION_DAYS:-14}
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP_NAME="lunia_backup_${TIMESTAMP}.tar.gz"
TARGET="${BACKUP_DIR}/${BACKUP_NAME}"

mkdir -p "${BACKUP_DIR}"

pushd "${REPO_ROOT}" >/dev/null
# Collect artifacts; missing paths are ignored with warnings.
INCLUDE=("lunia_core/data" "lunia_core/logs" "lunia_core/.env" "data/traefik")
EXISTING=()
for path in "${INCLUDE[@]}"; do
  if [ -e "$path" ]; then
    EXISTING+=("$path")
  else
    echo "[backup] skipping missing path: $path" >&2
  fi
done

if [ ${#EXISTING[@]} -eq 0 ]; then
  echo "[backup] nothing to backup" >&2
  exit 1
fi

tar -czf "${TARGET}" "${EXISTING[@]}"
echo "[backup] created ${TARGET}"

# Retention: remove archives older than RETENTION_DAYS
if [ -n "${RETENTION_DAYS}" ]; then
  find "${BACKUP_DIR}" -name 'lunia_backup_*.tar.gz' -type f -mtime +"${RETENTION_DAYS}" -print -delete
fi

popd >/dev/null
