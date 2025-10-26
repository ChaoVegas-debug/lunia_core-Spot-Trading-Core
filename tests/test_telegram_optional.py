from __future__ import annotations

import importlib
import sys
from pathlib import Path

# Ensure repository root on sys.path so lunia_core package can be imported locally
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_telegram():
    """
    Universal Telegram loader:
    1) Try to import lunia_core.app.services.telegram via importlib.
    2) Fallback to direct import if already installed locally.
    """
    try:
        return importlib.import_module("lunia_core.app.services.telegram")
    except Exception:
        from lunia_core.app.services import telegram as tg  # type: ignore
        return tg


telegram = _load_telegram()


def test_telegram_optional_surface() -> None:
    """Ensure telegram service facade works without aiogram."""
    assert hasattr(telegram, "is_available")
    assert isinstance(telegram.is_available(), bool)
    assert hasattr(telegram, "reason_unavailable")
    telegram.reason_unavailable()
