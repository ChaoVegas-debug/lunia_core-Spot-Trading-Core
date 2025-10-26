"""Lightweight scheduler bootstrap utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List


@dataclass
class ScheduledTask:
    """A minimal representation of a scheduled callable."""

    name: str
    handler: Callable[[], None]


class Scheduler:
    """In-memory registry for scheduled tasks."""

    def __init__(self) -> None:
        self._tasks: List[ScheduledTask] = []

    def register(self, task: ScheduledTask) -> None:
        self._tasks.append(task)

    def run_all(self) -> None:
        for task in list(self._tasks):
            task.handler()


def bootstrap() -> Scheduler:
    """Create a scheduler instance for the application."""

    return Scheduler()
