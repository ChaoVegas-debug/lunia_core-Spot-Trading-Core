"""Scheduler task for hourly digest reporting."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable, Optional

from ...core.ai.agent import Agent

BASE_LOG_DIR = Path(__file__).resolve().parents[4] / "logs"
LOG_PATH = BASE_LOG_DIR / "digest.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def _load_recent_orders(limit: int = 20) -> int:
    trades_path = BASE_LOG_DIR / "trades.jsonl"
    if not trades_path.exists():
        return 0
    with trades_path.open("r", encoding="utf-8") as fp:
        lines = fp.readlines()[-limit:]
    return sum(1 for line in lines if line.strip())


def run_hourly_digest(agent: Agent, notifier: Optional[Callable[[str], None]] = None) -> str:
    """Generate a digest summary and optionally notify via callback."""
    portfolio = agent.portfolio
    balances = agent.client.get_balances()
    equity = portfolio.get_equity_usd({asset: bal["free"] + bal["locked"] for asset, bal in balances.items()})
    digest = (
        f"Equity USD: {equity:.2f}\n"
        f"Realized PnL: {portfolio.realized_pnl:.2f}\n"
        f"Unrealized PnL: {portfolio.total_unrealized():.2f}\n"
        f"Signals buffered: {len(agent.supervisor.price_history)}\n"
        f"Recent orders: {_load_recent_orders()}"
    )
    logger.info("digest generated: %s", digest.replace("\n", " | "))
    if notifier:
        notifier(digest)
    return digest


def start_digest_loop(agent: Agent, interval_seconds: int = 3600, notifier: Optional[Callable[[str], None]] = None) -> None:
    logger.info("Starting digest loop interval=%s", interval_seconds)
    while True:  # pragma: no cover - long-running loop
        run_hourly_digest(agent, notifier=notifier)
        time.sleep(interval_seconds)
