"""Arbitrage service package."""
try:  # pragma: no cover - offline environments without Flask
    from .api import bp
except Exception:  # pragma: no cover
    bp = None  # type: ignore

from .worker import (
    auto_tick,
    execute_by_id,
    execute_opportunity,
    get_execution,
    get_filters,
    get_state,
    run_worker,
    scan_now,
    toggle_auto_mode,
    update_filters,
)

__all__ = [
    "bp",
    "auto_tick",
    "execute_by_id",
    "execute_opportunity",
    "get_execution",
    "get_filters",
    "get_state",
    "run_worker",
    "scan_now",
    "toggle_auto_mode",
    "update_filters",
]
