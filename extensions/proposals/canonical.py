"""
PHASE 10 — PROPOSAL SYSTEM: Canonical Serialization

Deterministic JSON serialization matching Phase 9.2/9.3 precision policy.

REQUIREMENTS:
- FLOAT_PRECISION = 8 (matches Phase 9.2/9.3)
- Sorted keys for stable output
- NaN/Infinity forbidden
- SHA256-based ID generation
"""

import hashlib
import json
import math
from typing import Any, Dict


# ────────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ────────────────────────────────────────────────────────────────────────────────

FLOAT_PRECISION = 8  # Must match Phase 9.2/9.3


# ────────────────────────────────────────────────────────────────────────────────
# CANONICAL JSON
# ────────────────────────────────────────────────────────────────────────────────


def to_canonical_json(obj: Any) -> str:
    """
    Convert object to canonical JSON string.
    
    - Floats rounded to FLOAT_PRECISION decimals
    - Keys sorted alphabetically
    - Enums converted to .value
    - NaN/Infinity forbidden
    - Stable separators
    
    Args:
        obj: Python object (dict, list, primitives, or dataclass-convertible)
    
    Returns:
        Canonical JSON string
    
    Raises:
        ValueError: If NaN or Infinity detected
    """
    def _process(value: Any) -> Any:
        """Recursively process value for canonical representation."""
        if value is None:
            return None
        elif isinstance(value, bool):
            return value
        elif isinstance(value, int):
            return value
        elif isinstance(value, float):
            if math.isnan(value):
                raise ValueError("NaN is not allowed in canonical JSON")
            if math.isinf(value):
                raise ValueError("Infinity is not allowed in canonical JSON")
            return round(value, FLOAT_PRECISION)
        elif isinstance(value, str):
            return value
        elif hasattr(value, 'value'):  # Enum
            return value.value
        elif isinstance(value, dict):
            return {k: _process(v) for k, v in value.items()}
        elif isinstance(value, (list, tuple)):
            return [_process(item) for item in value]
        elif hasattr(value, '__dict__'):  # Dataclass or object
            return _process(value.__dict__)
        else:
            return value
    
    processed = _process(obj)
    return json.dumps(processed, sort_keys=True, separators=(',', ':'))


# ────────────────────────────────────────────────────────────────────────────────
# DETERMINISTIC ID GENERATION
# ────────────────────────────────────────────────────────────────────────────────


def sha16_from_fields(fields: Dict[str, Any]) -> str:
    """
    Generate deterministic 16-character hex ID from fields.
    
    Uses SHA256 hash of canonical JSON representation.
    
    Args:
        fields: Dictionary of core fields for ID generation
    
    Returns:
        16-character hex string (first 16 chars of SHA256)
    
    Example:
        >>> sha16_from_fields({"intent_id": "abc", "ts_ms": 1234})
        'a1b2c3d4e5f67890'
    """
    canonical = to_canonical_json(fields)
    hash_digest = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    return hash_digest[:16]
