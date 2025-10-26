#!/usr/bin/env bash
set -euo pipefail
FILE="lunia_core/requirements/base_minimal.txt"
if [ ! -f "$FILE" ]; then
  echo "❌ Missing $FILE"
  exit 1
fi
if grep -Eiq '(aiogram|aiohttp|aio+gram|ai+ogram)' "$FILE"; then
  echo "❌ Telegram deps found in $FILE"
  exit 1
fi
echo "✅ Guard OK — no Telegram deps in minimal profile."
