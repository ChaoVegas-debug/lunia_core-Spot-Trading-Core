"""Compatibility shim for python-dotenv."""
from __future__ import annotations

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover - offline fallback
    def load_dotenv(*args, **kwargs) -> None:  # noqa: D401
        """Fallback load_dotenv that performs no action."""
        return None

__all__ = ["load_dotenv"]
