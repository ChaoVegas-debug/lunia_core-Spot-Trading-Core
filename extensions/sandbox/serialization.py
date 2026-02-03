"""
PHASE 9.2 — CANONICAL SERIALIZATION

Deterministic JSON serialization and hashing for audit trail integrity.

SPEC IMPROVEMENT:
- FLOAT_PRECISION = 8 for ALL floats (no conditional heuristics)
- This ensures determinism across all numeric types

GUARANTEES:
- Same input => same canonical JSON => same hash
- Sorted keys, stable enum encoding
- No NaN/Infinity
- Replay-safe
"""

import hashlib
import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any


# SPEC IMPROVEMENT: Single float precision policy (no heuristics)
FLOAT_PRECISION = 8


class CanonicalSerializationError(Exception):
    """Raised when serialization fails."""
    pass


def _default_encoder(obj: Any) -> Any:
    """
    Custom JSON encoder for protocol types.
    
    Handles:
    - Enums (→ .value)
    - Dataclasses (→ ordered dict)
    - Other types raise TypeError
    """
    if isinstance(obj, Enum):
        return obj.value
    elif is_dataclass(obj):
        # asdict preserves field order (Python 3.7+)
        return asdict(obj)
    else:
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _round_floats(obj: Any) -> Any:
    """
    Recursively round all floats to FLOAT_PRECISION.
    
    SPEC IMPROVEMENT: Single precision for all floats.
    """
    if isinstance(obj, float):
        # Forbid NaN/Infinity
        if not (obj == obj):  # NaN check
            raise CanonicalSerializationError("NaN values are not allowed")
        if obj == float('inf') or obj == float('-inf'):
            raise CanonicalSerializationError("Infinity values are not allowed")
        return round(obj, FLOAT_PRECISION)
    elif isinstance(obj, dict):
        return {k: _round_floats(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_round_floats(item) for item in obj]
    else:
        return obj


def to_canonical_json(obj: Any) -> str:
    """
    Convert object to canonical JSON string.
    
    GUARANTEES:
    - Deterministic output (sorted keys, stable separators)
    - All floats rounded to FLOAT_PRECISION
    - Enums converted to .value
    - Dataclasses converted to dicts
    - No NaN/Infinity
    
    Args:
        obj: Object to serialize (dataclass, dict, list, or primitive)
        
    Returns:
        Canonical JSON string
        
    Raises:
        CanonicalSerializationError: If object contains NaN/Infinity or is not serializable
    """
    try:
        # Convert to dict if dataclass
        if is_dataclass(obj):
            obj = asdict(obj)
        
        # Round all floats
        obj = _round_floats(obj)
        
        # Serialize with stable settings
        return json.dumps(
            obj,
            sort_keys=True,
            separators=(',', ':'),
            ensure_ascii=False,
            allow_nan=False,  # Forbid NaN/Infinity
            default=_default_encoder,
        )
    except (TypeError, ValueError) as e:
        raise CanonicalSerializationError(f"Serialization failed: {e}") from e


def canonical_hash(obj: Any) -> str:
    """
    Generate deterministic SHA256 hash of object.
    
    GUARANTEE: Same input => same hash (replay-safe)
    
    Args:
        obj: Object to hash
        
    Returns:
        64-character hex SHA256 hash
        
    Raises:
        CanonicalSerializationError: If serialization fails
    """
    canonical = to_canonical_json(obj)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def verify_determinism(obj: Any, iterations: int = 10) -> bool:
    """
    Verify that object serializes deterministically.
    
    Args:
        obj: Object to test
        iterations: Number of serialization iterations
        
    Returns:
        True if all iterations produce identical output
    """
    try:
        hashes = [canonical_hash(obj) for _ in range(iterations)]
        return len(set(hashes)) == 1
    except CanonicalSerializationError:
        return False
