"""Runtime guard utilities for monitoring and graceful shutdown."""

from __future__ import annotations

import logging
import signal
import threading
import time
from typing import Callable, Dict, List, Optional


class RuntimeGuard:
    """Centralised runtime state tracker.

    The guard keeps track of shutdown requests, surfaced errors, and
    optionally relays status updates to registered notifiers (e.g. Telegram).
    """

    def __init__(
        self,
        *,
        sleep_fn: Optional[Callable[[float], None]] = None,
        time_fn: Optional[Callable[[], float]] = None,
    ) -> None:
        self._shutdown = threading.Event()
        self._errors: List[str] = []
        self._notifiers: List[Callable[[str], None]] = []
        self._sleep_fn = sleep_fn or time.sleep
        self._time_fn = time_fn or time.time
        self._last_heartbeat: Optional[float] = None
        self._shutdown_reason: Optional[str] = None
        self._installed_signals: bool = False

    # ------------------------------------------------------------------
    # Signal and shutdown handling
    # ------------------------------------------------------------------
    def install_signal_handlers(self) -> None:
        """Register SIGINT/SIGTERM handlers for graceful shutdown."""

        if self._installed_signals:
            return

        def _handler(signum: int, _frame) -> None:  # noqa: ANN001
            self.request_shutdown(f"signal:{signum}")

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, _handler)
            except Exception:  # pragma: no cover - not all platforms allow it
                continue
        self._installed_signals = True

    def request_shutdown(self, reason: Optional[str] = None) -> None:
        """Signal the runtime loop to stop."""

        if reason and not self._shutdown_reason:
            self._shutdown_reason = reason
        self._shutdown.set()
        if reason:
            logging.info("runtime shutdown requested: %s", reason)
        self._notify(f"shutdown:{reason or 'requested'}")

    @property
    def should_stop(self) -> bool:
        return self._shutdown.is_set()

    def sleep(self, duration: float) -> None:
        if not self.should_stop and duration > 0:
            self._sleep_fn(duration)

    # ------------------------------------------------------------------
    # Notifier plumbing
    # ------------------------------------------------------------------
    def add_notifier(self, callback: Callable[[str], None]) -> None:
        """Register an optional notifier callback."""

        self._notifiers.append(callback)

    def _notify(self, message: str) -> None:
        for callback in list(self._notifiers):
            try:
                callback(message)
            except Exception as exc:  # pragma: no cover - defensive
                logging.debug("notifier failed: %s", exc)

    # ------------------------------------------------------------------
    # Error tracking & heartbeat
    # ------------------------------------------------------------------
    def execute_job(self, name: str, handler: Callable[[], None]) -> None:
        """Execute a scheduled job capturing exceptions."""

        try:
            handler()
        except Exception as exc:  # noqa: BLE001
            logging.exception("scheduled job %s failed", name)
            self._errors.append(f"{name}: {exc}")
            self.request_shutdown(f"job:{name}")

    def heartbeat(self, source: str = "runtime") -> None:
        """Record a heartbeat timestamp."""

        now = self._time_fn()
        self._last_heartbeat = now
        self._notify(f"heartbeat:{source}")

    @property
    def last_heartbeat(self) -> Optional[float]:
        return self._last_heartbeat

    @property
    def has_errors(self) -> bool:
        return bool(self._errors)

    @property
    def errors(self) -> List[str]:
        return list(self._errors)

    @property
    def status(self) -> Dict[str, Optional[float]]:
        return {
            "last_heartbeat": self._last_heartbeat,
            "shutdown": 1.0 if self.should_stop else 0.0,
        }
