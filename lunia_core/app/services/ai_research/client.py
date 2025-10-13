"""OpenAI client wrapper (stubbed for offline operation)."""
from __future__ import annotations

import hashlib
from typing import Dict, List

from app.compat.dotenv import load_dotenv

load_dotenv()


def synthesize_research(data: List[Dict[str, object]], strategy: str) -> str:
    """Return a deterministic summary string for provided data."""
    digest = hashlib.sha256(str(data).encode("utf-8")).hexdigest()[:8]
    return f"Strategy {strategy} summary {digest}"
