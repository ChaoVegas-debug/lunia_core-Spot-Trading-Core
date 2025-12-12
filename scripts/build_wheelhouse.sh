#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_REQS=("lunia_core/requirements/base_minimal.txt" "lunia_core/requirements/base.txt" "lunia_core/requirements/test.txt")
REQ_FILES=(${WHEELHOUSE_REQUIREMENTS:-"${DEFAULT_REQS[@]}"})
TARGET_DIR="${WHEELHOUSE_DIR:-$ROOT_DIR/wheelhouse}"
FREEZE_FILE="${TARGET_DIR}/requirements-resolved.txt"
REQUIRED_WHEELS=(flask pydantic requests sqlalchemy redis pyjwt pyyaml apscheduler passlib pytest)
REQUIRED_WHEELS+=(python-dotenv prometheus-client)
MANIFEST_FILE="${TARGET_DIR}/manifest.txt"

usage() {
  cat <<USAGE
Usage: WHEELHOUSE_DIR=./wheelhouse WHEELHOUSE_REQUIREMENTS="req1 req2" scripts/build_wheelhouse.sh [extra pip download args]

Environment:
  WHEELHOUSE_DIR              Target directory for wheels (default: ./wheelhouse)
  WHEELHOUSE_REQUIREMENTS     Space-separated list of requirement files (default: base_minimal + base)
  PIP_INDEX_URL, PIP_EXTRA_INDEX_URL, PIP_TRUSTED_HOST, HTTPS_PROXY, HTTP_PROXY respected by pip

The script downloads wheels for the provided requirement files, writes a pip freeze snapshot,
and avoids installing into the host Python.
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

mkdir -p "$TARGET_DIR"
EXTRA_PIP_ARGS=()
if [[ $# -gt 0 ]]; then
  EXTRA_PIP_ARGS=("$@")
fi

echo "[wheelhouse] Target: $TARGET_DIR"
echo "[wheelhouse] Requirements: ${REQ_FILES[*]}"

for req in "${REQ_FILES[@]}"; do
  if [ ! -f "$ROOT_DIR/$req" ]; then
    echo "Requirement file not found: $req" >&2
    exit 1
  fi
  echo "[wheelhouse] Downloading wheels for $req"
  python -m pip download --dest "$TARGET_DIR" -r "$ROOT_DIR/$req" "${EXTRA_PIP_ARGS[@]}"
  cp "$ROOT_DIR/$req" "$TARGET_DIR/$(basename "$req")"
done

# Produce a resolved snapshot via a throwaway venv to aid offline installs
TMP_VENV="$(mktemp -d)"
python -m venv "$TMP_VENV/venv"
source "$TMP_VENV/venv/bin/activate"
python -m pip install --upgrade pip >/dev/null
for req in "${REQ_FILES[@]}"; do
  python -m pip install -r "$ROOT_DIR/$req" "${EXTRA_PIP_ARGS[@]}" >/dev/null
done
python -m pip freeze > "$FREEZE_FILE"
deactivate
rm -rf "$TMP_VENV"

echo "[wheelhouse] Resolved requirements written to $FREEZE_FILE"

missing=()
for pkg in "${REQUIRED_WHEELS[@]}"; do
  if ! ls "$TARGET_DIR" | grep -qi "^${pkg}-.*\.whl"; then
    missing+=("$pkg")
  fi
done

if [ ${#missing[@]} -ne 0 ]; then
  echo "[wheelhouse] Missing wheels for: ${missing[*]}" >&2
  echo "[wheelhouse] Re-run with network access or adjust PIP_INDEX_URL/PROXY settings." >&2
  exit 1
fi

ls "$TARGET_DIR"/*.whl | xargs -n1 -I{} basename {} > "$MANIFEST_FILE"
echo "[wheelhouse] Manifest written to $MANIFEST_FILE"
echo "[wheelhouse] Wheelhouse prepared at $TARGET_DIR"
