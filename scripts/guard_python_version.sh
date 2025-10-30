#!/usr/bin/env bash
set -euo pipefail
REQ="3.11"
CUR=$(python -c "import sys;print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if [ "$CUR" != "$REQ" ]; then
  echo "❌ Python $CUR detected — requires $REQ.x (aiogram 2.x / aiohttp 3.8.x compatible)"
  exit 1
fi
echo "✅ Python $CUR OK"
