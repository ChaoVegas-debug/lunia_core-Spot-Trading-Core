#!/usr/bin/env bash
set -euo pipefail

FILE="lunia_core/requirements/base_minimal.txt"

if [[ ! -f "$FILE" ]]; then
  echo "❌ Missing $FILE"
  exit 1
fi

# В минимальном профиле НЕ должно быть телеграм-зависимостей.
# Проверяем самые распространённые пакеты/вариации названий.
if grep -Eiq '(^|[[:space:]])(aiogram([[:space:]]|==|\[)|python-telegram-bot|telethon|pytelegrambotapi|aiotg)' "$FILE"; then
  echo "❌ Telegram deps found in minimal profile: $FILE"
  grep -niE '(aiogram|python-telegram-bot|telethon|pytelegrambotapi|aiotg)' "$FILE" || true
  exit 1
fi

echo "✅ Guard OK — no Telegram deps in minimal profile."