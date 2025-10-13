from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, Optional

from app.core.metrics import alerts_sent_total
from app.db.reporting import arbitrage_daily_summary

LOG_DIR = Path(__file__).resolve().parents[4] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
ALERT_LOG = LOG_DIR / "alerts.log"

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.FileHandler(ALERT_LOG, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def _enabled() -> bool:
    return os.getenv("ALERTS_ENABLED", "false").lower() == "true"


def send_alert(level: str, message: str) -> None:
    """Record an alert event and emit metrics."""
    logger.warning("[%s] %s", level.upper(), message)
    alerts_sent_total.labels(level=level).inc()


def evaluate_and_alert(stats: Optional[Dict[str, float]] = None) -> None:
    """Evaluate thresholds based on stats and emit alerts if needed."""
    if not _enabled():
        return
    stats = stats or arbitrage_daily_summary()
    threshold = float(os.getenv("ALERTS_FAIL_THRESHOLD", "5"))
    warn_roi = float(os.getenv("ALERTS_NET_ROI_WARN_PCT", "0.5"))
    if stats.get("fail", 0) >= threshold:
        send_alert("error", f"Arbitrage failures {stats['fail']} exceed threshold {threshold}")
    if stats.get("avg_roi", 0.0) < warn_roi:
        send_alert("warning", f"Average ROI {stats['avg_roi']:.2f}% below {warn_roi}%")
    if stats.get("success", 0) + stats.get("fail", 0) > 0:
        rate = stats.get("success_rate", 0.0) * 100
        if rate < 50.0:
            send_alert("warning", f"Success rate degraded to {rate:.1f}%")


__all__ = ["send_alert", "evaluate_and_alert"]
