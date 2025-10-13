"""Synthetic data generators for backtesting (placeholder)."""
from __future__ import annotations

import logging
from typing import List

logger = logging.getLogger(__name__)


def generate_gbm(start_price: float, steps: int) -> List[float]:
    """Placeholder geometric Brownian motion generator."""
    logger.info("Generating synthetic GBM prices start=%s steps=%s", start_price, steps)
    return [start_price for _ in range(steps)]
