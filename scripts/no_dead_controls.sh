#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ALLOWLIST_FILE="$ROOT_DIR/.no_dead_controls_allowlist"
TARGETS=("$ROOT_DIR/frontend/src")
patterns=(
  "onClick=\\{\\s*\\(.*?\\)\\s*=>\\s*\\{\\s*\\}\\s*\\}"
  "onSubmit=\\{\\s*\\(.*?\\)\\s*=>\\s*\\{\\s*\\}\\s*\\}"
  "onClick=\\{\\s*\\(.*?\\)\\s*=>\\s*undefined\\s*\\}"
  "console\\.log\\(\\s*['\"]TODO"
)

if ! command -v rg >/dev/null 2>&1; then
  echo "ripgrep (rg) is required for no-dead-controls; install via package manager" >&2
  exit 1
fi

is_allowed() {
  local file="$1"
  if [[ -f "$ALLOWLIST_FILE" ]] && grep -Fxq "$file" "$ALLOWLIST_FILE"; then
    return 0
  fi
  return 1
}

failures=()
for pat in "${patterns[@]}"; do
  while IFS= read -r match; do
    file=$(echo "$match" | cut -d':' -f1)
    if is_allowed "$file"; then
      continue
    fi
    failures+=("$match")
  done < <(rg --pcre2 "$pat" "${TARGETS[@]}" || true)
  done

if [ ${#failures[@]} -ne 0 ]; then
  echo "Dead control patterns detected:" >&2
  printf '%s\n' "${failures[@]}" >&2
  echo "Resolve handlers or add intentional cases to $ALLOWLIST_FILE" >&2
  exit 1
fi

echo "no-dead-controls: OK"
