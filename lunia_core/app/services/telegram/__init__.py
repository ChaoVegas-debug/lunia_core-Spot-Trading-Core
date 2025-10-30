from typing import Optional

_AVAILABLE: bool = False
_REASON: Optional[str] = None

# Пытаемся мягко импортировать aiogram (опциональная зависимость).
try:
    import aiogram  # noqa: F401
    _AVAILABLE = True
except Exception as e:  # pragma: no cover — опциональная зависимость
    _AVAILABLE = False
    _REASON = str(e)


def is_available() -> bool:
    """Есть ли aiogram в окружении (можно включать Telegram-модуль)."""
    return _AVAILABLE


def reason_unavailable() -> Optional[str]:
    """Почему недоступен Telegram-модуль (None, если доступен)."""
    return None if _AVAILABLE else (_REASON or "aiogram not installed")


__all__ = ["is_available", "reason_unavailable"]