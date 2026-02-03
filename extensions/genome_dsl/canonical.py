"""
PHASE 11 — GENOME DSL: Canonical Serialization

Deterministic JSON serialization and genome ID generation.

CRITICAL: 
- Sorted keys for stability
- 8-decimal float precision (matches Phase 9.2/9.3/10)
- No NaN/Infinity
- Deterministic genome_id via SHA256
"""

import hashlib
import json
import math
from typing import Any, Dict
from dataclasses import asdict, is_dataclass


# ────────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ────────────────────────────────────────────────────────────────────────────────

FLOAT_PRECISION = 8  # Must match Phase 9.2/9.3/10


# ────────────────────────────────────────────────────────────────────────────────
# CANONICAL SERIALIZATION
# ────────────────────────────────────────────────────────────────────────────────


def to_canonical_dict(obj: Any) -> Dict[str, Any]:
    """
    Convert genome AST to canonical dict representation.
    
    Args:
        obj: AST node or primitive
    
    Returns:
        Canonical dict (JSON-serializable)
    
    Raises:
        ValueError: If NaN or Infinity detected
    """
    def _process(value: Any) -> Any:
        """Recursively process value."""
        if value is None:
            return None
        elif isinstance(value, bool):
            return value
        elif isinstance(value, int):
            return value
        elif isinstance(value, float):
            if math.isnan(value):
                raise ValueError("NaN is not allowed in canonical serialization")
            if math.isinf(value):
                raise ValueError("Infinity is not allowed in canonical serialization")
            return round(value, FLOAT_PRECISION)
        elif isinstance(value, str):
            return value
        elif isinstance(value, dict):
            return {k: _process(v) for k, v in sorted(value.items())}
        elif isinstance(value, (list, tuple)):
            return [_process(item) for item in value]
        elif is_dataclass(value):
            # Convert dataclass to dict
            node_dict = asdict(value)
            # Add type marker for reconstruction
            node_dict["__type__"] = value.__class__.__name__
            return _process(node_dict)
        else:
            # Fallback for unknown types
            return str(value)
    
    return _process(obj)


def to_canonical_json(obj: Any) -> str:
    """
    Convert to canonical JSON string.
    
    Args:
        obj: AST node or primitive
    
    Returns:
        Canonical JSON string (sorted keys, stable separators)
    """
    canonical_dict = to_canonical_dict(obj)
    return json.dumps(canonical_dict, sort_keys=True, separators=(',', ':'))


def from_canonical_dict(data: Dict[str, Any]) -> Any:
    """
    Reconstruct AST from canonical dict.
    
    Args:
        data: Canonical dict representation
    
    Returns:
        Reconstructed AST node
    
    Note: Requires __type__ marker in dict
    """
    if not isinstance(data, dict):
        return data
    
    if "__type__" not in data:
        # Plain dict, recurse
        return {k: from_canonical_dict(v) for k, v in data.items()}
    
    # Reconstruct node
    from extensions.genome_dsl import types
    
    node_type_name = data.pop("__type__")
    node_class = getattr(types, node_type_name, None)
    
    if node_class is None:
        raise ValueError(f"Unknown node type: {node_type_name}")
    
    # Recursively reconstruct child nodes
    reconstructed_fields = {}
    for key, value in data.items():
        if isinstance(value, dict) and "__type__" in value:
            reconstructed_fields[key] = from_canonical_dict(value)
        elif isinstance(value, list):
            reconstructed_fields[key] = [
                from_canonical_dict(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            reconstructed_fields[key] = value
    
    return node_class(**reconstructed_fields)


# ────────────────────────────────────────────────────────────────────────────────
# GENOME IDENTITY
# ────────────────────────────────────────────────────────────────────────────────


def genome_id(genome) -> str:
    """
    Generate deterministic 16-hex genome ID.
    
    Args:
        genome: StrategyGenome instance
    
    Returns:
        16-character hex string (SHA256 of canonical JSON)
    
    Example:
        >>> genome_id(my_genome)
        'a1b2c3d4e5f67890'
    """
    canonical = to_canonical_json(genome)
    hash_digest = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    return hash_digest[:16]


def canonical_hash(obj: Any) -> str:
    """
    Generate deterministic SHA256 hash of any object.
    
    Args:
        obj: Any object (will be canonicalized)
    
    Returns:
        64-character hex string (full SHA256 hash)
    
    Example:
        >>> canonical_hash({"a": 1, "b": 2})
        'abc123...'
    """
    canonical = to_canonical_json(obj)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

