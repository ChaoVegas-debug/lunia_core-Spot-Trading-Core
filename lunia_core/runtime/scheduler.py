"""Lightweight runtime scheduler for periodic tasks."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from .guard import RuntimeGuard


@dataclass
class ScheduledJob:
    """Representation of a periodic job."""

    name: str
    interval: float
    handler: Callable[[], None]
    last_run: float = field(default_factory=lambda: 0.0)


class RuntimeScheduler:
    """Simple cooperative scheduler that relies on :class:`RuntimeGuard`."""

    def __init__(
        self,
        guard: RuntimeGuard,
        *,
        idle_sleep: float = 0.5,
        time_fn: Optional[Callable[[], float]] = None,
    ) -> None:
        if idle_sleep < 0:
            raise ValueError("idle_sleep must be positive")
        self.guard = guard
        self._idle_sleep = idle_sleep
        self._time_fn = time_fn or time.monotonic
        self._jobs: List[ScheduledJob] = []

    # ------------------------------------------------------------------
    def add_interval_job(self, name: str, interval: float, handler: Callable[[], None]) -> None:
        """Register a callable that runs every ``interval`` seconds."""

        if interval <= 0:
            raise ValueError("interval must be positive")
        job = ScheduledJob(name=name, interval=interval, handler=handler)
        start = self._time_fn()
        job.last_run = start - interval  # run on first tick
        self._jobs.append(job)
        logging.debug("registered job %s (interval=%s)", name, interval)

    # ------------------------------------------------------------------
    def tick(self, current_time: Optional[float] = None) -> int:
        """Execute due jobs once.

        Returns the number of jobs executed.
        """

        now = current_time if current_time is not None else self._time_fn()
        executed = 0
        for job in self._jobs:
            if now - job.last_run >= job.interval:
                self.guard.execute_job(job.name, job.handler)
                job.last_run = now
                executed += 1
        return executed

    # ------------------------------------------------------------------
    def run(self, *, max_ticks: Optional[int] = None) -> None:
        """Run until the guard requests shutdown or ``max_ticks`` reached."""

        ticks = 0
        while not self.guard.should_stop:
            executed = self.tick()
            ticks += 1
            if max_ticks is not None and ticks >= max_ticks:
                logging.debug("scheduler reached max_ticks=%s", max_ticks)
                break
            if executed == 0:
                self.guard.sleep(self._idle_sleep)

        logging.info("scheduler exiting (errors=%s)", self.guard.errors)
