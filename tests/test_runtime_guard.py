from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lunia_core import main as runtime_main
from lunia_core.runtime.guard import RuntimeGuard
from lunia_core.runtime.scheduler import RuntimeScheduler


def test_guard_records_error_and_stops() -> None:
    guard = RuntimeGuard()

    def boom() -> None:
        raise RuntimeError("boom")

    guard.execute_job("boom", boom)
    assert guard.has_errors
    assert guard.should_stop
    assert any("boom" in msg for msg in guard.errors)


def test_scheduler_ticks_jobs() -> None:
    guard = RuntimeGuard()
    scheduler = RuntimeScheduler(guard, idle_sleep=0, time_fn=lambda: 0.0)

    counter: list[int] = []
    scheduler.add_interval_job("count", 1.0, lambda: counter.append(1))

    scheduler.tick(current_time=0.0)
    scheduler.tick(current_time=0.2)
    scheduler.tick(current_time=1.1)

    assert len(counter) == 2
    assert not guard.has_errors


def test_guard_notifier_receives_shutdown() -> None:
    guard = RuntimeGuard()
    received: list[str] = []
    guard.add_notifier(received.append)

    guard.request_shutdown("unit-test")
    assert any(msg.startswith("shutdown:") for msg in received)


def test_runtime_main_dry_run() -> None:
    exit_code = runtime_main.run(["--dry-run", "--ticks", "2"])
    assert exit_code == 0
