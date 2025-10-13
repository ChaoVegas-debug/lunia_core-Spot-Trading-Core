"""Pytest configuration for Lunia core tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def pytest_configure(config: pytest.Config) -> None:  # pragma: no cover - pytest hook
    """Register custom markers used across the test-suite."""

    config.addinivalue_line("markers", "requires_flask: marks tests that need Flask")
