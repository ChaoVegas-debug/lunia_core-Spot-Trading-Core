"""Runtime entrypoint for Lunia Core."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Callable, Iterable, Optional
from pathlib import Path

if __package__ in {None, ''}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lunia_core.runtime.guard import RuntimeGuard
from lunia_core.runtime.scheduler import RuntimeScheduler


def _load_env() -> bool:
    """Load environment variables from .env if python-dotenv is available."""

    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:  # pragma: no cover - optional dependency
        logging.debug("python-dotenv not available; skipping .env load")
        return False

    env_file = os.environ.get("LUNIA_ENV_FILE")
    if env_file:
        return load_dotenv(env_file)
    return load_dotenv()


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def _telegram_notifier() -> Optional[Callable[[str], None]]:
    try:
        from lunia_core.app.services import telegram
    except Exception:  # pragma: no cover - defensive
        logging.debug("telegram facade unavailable")
        return None

    if telegram.is_available():
        logging.info("telegram integration available")

        def notify(message: str) -> None:
            logging.debug("telegram notifier received: %s", message)

        return notify

    logging.info("telegram unavailable: %s", telegram.reason_unavailable())
    return None


def _parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lunia Core runtime")
    parser.add_argument("--dry-run", action="store_true", help="Run a limited number of scheduler ticks and exit")
    parser.add_argument("--ticks", type=int, default=3, help="Number of scheduler ticks when running in dry-run mode")
    parser.add_argument("--heartbeat-interval", type=float, default=5.0, help="Seconds between guard heartbeats")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args(list(argv) if argv is not None else None)


def _register_jobs(scheduler: RuntimeScheduler, guard: RuntimeGuard, heartbeat_interval: float) -> None:
    interval = max(heartbeat_interval, 1.0)
    scheduler.add_interval_job("guard-heartbeat", interval, lambda: guard.heartbeat("scheduler"))
    scheduler.add_interval_job("status-log", interval * 2, lambda: logging.debug("runtime status: %s", guard.status))


def run(argv: Optional[Iterable[str]] = None) -> int:
    args = _parse_args(argv)
    _setup_logging(args.verbose)
    _load_env()

    guard = RuntimeGuard()
    guard.install_signal_handlers()

    notifier = _telegram_notifier()
    if notifier:
        guard.add_notifier(notifier)

    scheduler = RuntimeScheduler(guard)
    _register_jobs(scheduler, guard, args.heartbeat_interval)

    guard.heartbeat("boot")

    max_ticks = args.ticks if args.dry_run else None
    scheduler.run(max_ticks=max_ticks)

    if args.dry_run and not guard.should_stop:
        guard.request_shutdown("dry-run")

    return 0 if not guard.has_errors else 1


def main() -> int:
    return run()


if __name__ == "__main__":
    sys.exit(main())
