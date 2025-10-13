"""Scheduler task placeholder for rebalancing."""
"""Rebalancer utilities for Lunia cores."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Dict

from ...boot import CORES
from ...core.ai.agent import Agent

LOG_PATH = Path(__file__).resolve().parents[4] / "logs" / "rebalancer.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def rebalance(agent: Agent) -> Dict[str, float]:
    """Compute simple target allocations and log."""
    portfolio = agent.portfolio
    balances = agent.client.get_balances()
    equity = portfolio.get_equity_usd({asset: bal["free"] + bal["locked"] for asset, bal in balances.items()})
    targets = {name: cfg["weight"] * equity for name, cfg in CORES.items() if cfg.get("enabled")}
    logger.info("Rebalance tick equity=%.2f targets=%s", equity, targets)
    return targets


def start_rebalancer(agent: Agent, interval_seconds: int = 900) -> None:
    logger.info("Starting rebalancer loop interval=%s", interval_seconds)
    while True:  # pragma: no cover - long-running loop
        rebalance(agent)
        time.sleep(interval_seconds)
