#!/usr/bin/env bash
set -euo pipefail

FILE="lunia_core/requirements/base_minimal.txt"

if [[ ! -f "$FILE" ]]; then
  echo "❌ Missing $FILE"
  exit 1
fi

# В минимальном профиле НЕ должно быть зависимостей, связанных с Telegram,
# а также aiohttp, которое требуется aiogram’у. Проверяем самые распространённые пакеты/вариации названий, включая aiohttp.
if grep -Eiq '(^|[[:space:]])(aiogram([[:space:]]|==|\[)|aiohttp([[:space:]]|==|\[)|python-telegram-bot|telethon|pytelegrambotapi|aiotg)' "$FILE"; then
  echo "❌ Forbidden deps found in minimal profile: $FILE"
  grep -niE '(aiogram|aiohttp|python-telegram-bot|telethon|pytelegrambotapi|aiotg)' "$FILE" || true
  exit 1
fi

echo "✅ Guard OK — no Telegram-related deps in minimal profile."
