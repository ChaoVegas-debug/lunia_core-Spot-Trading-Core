#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REQ_FILE="${1:-requirements/base.txt}"
TARGET_DIR="${WHEELHOUSE_DIR:-$ROOT_DIR/wheelhouse}"

if [ ! -f "$ROOT_DIR/$REQ_FILE" ]; then
  echo "Requirement file not found: $REQ_FILE" >&2
  exit 1
fi

mkdir -p "$TARGET_DIR"

echo "Downloading wheels for $REQ_FILE into $TARGET_DIR"
python -m pip install --upgrade pip >/dev/null
python -m pip download --dest "$TARGET_DIR" -r "$ROOT_DIR/$REQ_FILE"

echo "Wheelhouse prepared at $TARGET_DIR"
