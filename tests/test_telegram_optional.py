from __future__ import annotations
import sys
import importlib
from pathlib import Path

# Подготовка пути, чтобы импорт работал без установки пакета
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_telegram():
    """Универсальный загрузчик модуля telegram, даже если aiogram отсутствует."""
    try:
        return importlib.import_module("lunia_core.app.services.telegram")
    except Exception:
        from lunia_core.app.services import telegram as tg  # type: ignore
        return tg


telegram = _load_telegram()


def test_telegram_optional_surface():
    """Убедиться, что telegram-фасад доступен даже без aiogram."""
    assert hasattr(telegram, "is_available")
    assert isinstance(telegram.is_available(), bool)
    assert hasattr(telegram, "reason_unavailable")
    telegram.reason_unavailable()