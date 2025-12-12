#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ALLOWLIST_FILE="$ROOT_DIR/.no_placeholders_allowlist"
TARGETS=("$ROOT_DIR/frontend/src" "$ROOT_DIR/lunia_core/app/services/api")
PATTERN="TODO|placeholder|coming soon|stub|mock only"

say() { printf "[no-placeholders] %s\n" "$*"; }

readarray -t allowlist < <( ( [ -f "$ALLOWLIST_FILE" ] && cat "$ALLOWLIST_FILE" ) || true )

matches=$(rg -n "$PATTERN" "${TARGETS[@]}" || true)

if [ -z "$matches" ]; then
  say "No placeholder patterns found"
  exit 0
fi

failures=()
while IFS= read -r line; do
  skip=false
  rel_line=${line#${ROOT_DIR}/}
  if [[ "$rel_line" == *'placeholder="'* ]]; then
    skip=true
  fi
  for allow in "${allowlist[@]}"; do
    if [[ -n "$allow" && "$rel_line" == *"$allow"* ]]; then
      skip=true
      break
    fi
  done
  if [ "$skip" = false ]; then
    failures+=("$line")
  fi
done <<< "$matches"

if [ ${#failures[@]} -gt 0 ]; then
  echo "Placeholder/TODO patterns detected:" >&2
  for f in "${failures[@]}"; do
    echo " - $f" >&2
  done
  exit 1
fi

say "All placeholder patterns are allowlisted"
