"""Guard service checking API health."""
from __future__ import annotations

import logging
import os
from typing import Optional

from app.compat.requests import requests

logger = logging.getLogger(__name__)


def ping_health(url: Optional[str] = None) -> bool:
    """Ping the health endpoint and return True if healthy."""
    target = url or f"http://{os.getenv('HOST', '0.0.0.0')}:{os.getenv('PORT', '8080')}/health"
    logger.info("Pinging health endpoint %s", target)
    try:
        response = requests.get(target, timeout=5)
        response.raise_for_status()
        if response.json().get("status") == "ok":
            logger.info("Healthcheck ok")
            return True
    except requests.RequestException as exc:
        logger.error("Healthcheck failed: %s", exc)
    logger.warning("Service unhealthy. Consider restarting via systemctl restart lunia_api")
    return False
