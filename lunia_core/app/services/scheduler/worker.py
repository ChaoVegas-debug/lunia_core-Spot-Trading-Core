"""Scheduler entrypoint running rebalancer and digest loops."""
from __future__ import annotations

import threading

from ...core.metrics import ensure_metrics_server
from ..api.flask_app import agent
from .digest import start_digest_loop
from .rebalancer import start_rebalancer


def run_scheduler() -> None:
    ensure_metrics_server(9101)
    threads = [
        threading.Thread(target=start_rebalancer, args=(agent,), kwargs={"interval_seconds": 900}, daemon=True),
        threading.Thread(target=start_digest_loop, args=(agent,), kwargs={"interval_seconds": 3600}, daemon=True),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


if __name__ == "__main__":  # pragma: no cover
    run_scheduler()
