"""Core guard utilities for runtime checks."""

from __future__ import annotations

from typing import Iterable


def ensure_flags(enabled_flags: Iterable[str], required: Iterable[str]) -> bool:
    """Return True if all required flags are present within enabled_flags."""

    lookup = set(enabled_flags)
    return all(flag in lookup for flag in required)
