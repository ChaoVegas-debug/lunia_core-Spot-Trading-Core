from __future__ import annotations

"""Rebalancer: Automating Portfolio Maintenance."""

import logging
import time
from pathlib import Path
from typing import Dict, Any

from ...core.state import get_state, set_state
from ...core.portfolio.executor import PortfolioExecutor
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


def _check_and_trigger_rebalance(agent: Agent) -> None:
    """Iterate Active Portfolios, checking schedule vs last_rebalanced_at."""
    state = get_state()
    definitions = state.get("portfolio", {}).get("definitions", {})
    
    if state.get("global_stop"):
        logger.info("Global Stop ENGAGED. Scheduler skipping rebalance.")
        return
        logger.info("No definitions found. Skipping check.")
        return

    now = time.time()
    
    for pid, pdata in definitions.items():
        # pdata is a dict if coming from raw state, or Obj if cached. 
        # get_runtime_state returns raw dicts usually unless parsed.
        # Assuming dict access for safety.
        
        status = pdata.get("status")
        if status != "ACTIVE":
            continue
            
        rules = pdata.get("rules", {})
        interval_days = rules.get("rebalance_interval_days", 7)
        last_run = pdata.get("last_rebalanced_at")
        
        should_run = False
        if last_run is None:
            # First run logic: 
            # Option A: Run immediately? 
            # Option B: Mark now as start point? 
            # Let's Mark now as start point to avoid surprise rebalance on reboot, 
            # unless user explicitly requested 'Immediate' entry. 
            # But prompt says "Automated portfolio rebalancing". 
            # Let's set it to 'now' so it waits one interval.
            logger.info(f"Initializing schedule for {pid}. Next run in {interval_days} days.")
            pdata["last_rebalanced_at"] = now
            should_run = False
            # Update state immediately to persist init
            _update_portfolio_timestamp(state, pid, now)
        else:
            elapsed_days = (now - float(last_run)) / 86400.0
            if elapsed_days >= interval_days:
                should_run = True
                
        if should_run:
            logger.info(f"TRIGGERING Rebalance for {pid} (Elapsed: {elapsed_days:.2f}d / Limit: {interval_days}d)")
            try:
                executor = PortfolioExecutor(agent)
                result = executor.execute_rebalance(pid)
                if result.get("ok"):
                    logger.info(f"Rebalance SUCCESS for {pid}: {len(result.get('orders', []))} orders executed.")
                    _update_portfolio_timestamp(state, pid, now)
                else:
                    logger.warning(f"Rebalance FAILED for {pid}: {result}")
            except Exception as e:
                logger.exception(f"Exception rebalancing {pid}: {e}")

def _update_portfolio_timestamp(state: Dict[str, Any], pid: str, ts: float) -> None:
    # Deep update state
    # get_runtime_state returns a copy? It usually accesses the singleton dict.
    # We need to call set_state to trigger persistence/events if applicable.
    # But set_state merges.
    current_defs = state.get("portfolio", {}).get("definitions", {})
    if pid in current_defs:
        current_defs[pid]["last_rebalanced_at"] = ts
        set_state({"portfolio": {"definitions": current_defs}})


def start_rebalancer(agent: Agent, interval_seconds: int = 3600) -> None:
    """Main Loop."""
    logger.info(f"Starting Portfolio Scheduler (Tick: {interval_seconds}s)")
    while True:
        try:
            _check_and_trigger_rebalance(agent)
        except Exception as e:
            logger.exception("Scheduler Loop Crash")
        time.sleep(interval_seconds)
