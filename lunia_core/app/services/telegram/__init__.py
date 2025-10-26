from typing import Optional

_AVAILABLE = False
_REASON: Optional[str] = None
try:
    import aiogram  # optional import
    _AVAILABLE = True
except Exception as exc:  # pragma: no cover - optional dependency
    _AVAILABLE = False
    _REASON = str(exc)


def is_available() -> bool:
    return _AVAILABLE


def reason_unavailable() -> Optional[str]:
    return None if _AVAILABLE else (_REASON or "aiogram not installed")
