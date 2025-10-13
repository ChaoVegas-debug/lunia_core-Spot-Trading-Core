"""Budget guard placeholder."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def check_budget(spent_usd: float, soft_limit_usd: float = 100.0) -> bool:
    """Return False when spent exceeds soft limit, simulating a soft stop."""
    logger.info("Checking budget spent=%.2f soft_limit=%.2f", spent_usd, soft_limit_usd)
    if spent_usd > soft_limit_usd:
        logger.warning("Soft budget limit reached. Suggest pausing trading.")
        return False
    logger.info("Budget within limits")
    return True
