"""Decimal-Safe JSON Serialization (PHASE 4)

Paranoid serializer that converts Decimal -> str to prevent float leakage.
Floats and ints remain unchanged (valid JSON primitives).
"""
import json
from decimal import Decimal
from enum import Enum
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List


def to_json_safe(obj: Any) -> Any:
    """Recursively convert object to JSON-safe format.
    
    Rules:
    - Decimal -> str (CRITICAL: prevents float leakage in money/risk values)
    - float/int -> unchanged (already JSON-safe, allowed for metadata like age_seconds)
    - Enum -> .value
    - dataclass -> asdict -> recurse
    - dict/list/tuple -> recurse
    - bool/None/str -> pass through
    
    Args:
        obj: Object to convert
        
    Returns:
        JSON-safe object (no Decimals, no Enums, no dataclasses)
    """
    # JSON primitives - return as-is
    if obj is None or isinstance(obj, (bool, str, int, float)):
        return obj
    
    # Decimal ->str (CRITICAL for Phase 4)
    if isinstance(obj, Decimal):
        return str(obj)
    
    if isinstance(obj, Enum):
        return obj.value
    
    if is_dataclass(obj):
        return to_json_safe(asdict(obj))
    
    if isinstance(obj, dict):
        return {k: to_json_safe(v) for k, v in obj.items()}
    
    if isinstance(obj, (list, tuple)):
        return [to_json_safe(item) for item in obj]
    
    # Fallback: try str() for unknown types
    return str(obj)


def assert_no_floats(obj: Any, path: str = "root") -> None:
    """Assert no float values present in object tree.
    
    Raises:
        RuntimeError: If float detected in risk/equity/drawdown context
    """
    if isinstance(obj, float):
        raise RuntimeError(
            f"[PHASE4_VIOLATION] Float detected at {path}. "
            f"All monetary/risk values must be Decimal-as-string. "
            f"value={obj}"
        )
    
    if isinstance(obj, dict):
        for key, value in obj.items():
            assert_no_floats(value, f"{path}.{key}")
    
    elif isinstance(obj, (list, tuple)):
        for i, item in enumerate(obj):
            assert_no_floats(item, f"{path}[{i}]")


def decimal_json_dumps(obj: Any, **kwargs) -> str:
    """JSON dumps with Decimal-as-string conversion.
    
    Args:
        obj: Object to serialize
        **kwargs: Passed to json.dumps
        
    Returns:
        JSON string with all Decimals as strings
    """
    safe_obj = to_json_safe(obj)
    return json.dumps(safe_obj, **kwargs)
