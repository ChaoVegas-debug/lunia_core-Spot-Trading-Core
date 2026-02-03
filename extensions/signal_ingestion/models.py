"""
PHASE 15A — SIGNAL INGESTION CORE: Data Models

Canonical structures for market signal ingestion, normalization, and decay.
All models are deterministic, immutable, and governance-isolated.

GOVERNANCE WARNING:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This is a READ-ONLY context layer. It MUST NOT be imported by:
  - extensions/execution_gateway/
  - extensions/execution_router/
  - extensions/exchange_connectivity/
  - extensions/execution_monitoring/
  - extensions/execution_settlement/

Violation of this invariant will cause CI build failure.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import hashlib
import json
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Optional, Union

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ENUMERATIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SignalSource(str, Enum):
    """External signal sources (read-only data feeds)"""
    NEWS = "NEWS"
    WHALE = "WHALE"
    ONCHAIN = "ONCHAIN"
    SOCIAL = "SOCIAL"
    MACRO = "MACRO"
    EXCHANGE_FLOW = "EXCHANGE_FLOW"
    INTERNAL = "INTERNAL"


class SignalSeverity(str, Enum):
    """Impact severity classification"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CORE DATA STRUCTURES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass(frozen=True)
class SignalEvent:
    """
    Canonical immutable signal event.
    
    Governance:
      - frozen=True prevents mutation
      - All math via Decimal (no float)
      - Deterministic ID via SHA256
      - TTL-based expiry (no implicit behavior)
    """
    signal_id: str  # 16-char hex digest (deterministic)
    source: SignalSource
    category: str  # News type, whale action, etc
    symbol: Optional[str]  # BTC, ETH, etc (None for macro signals)
    ts_ms: int  # Signal timestamp (milliseconds since epoch)
    ttl_ms: int  # Time-to-live in milliseconds
    confidence: Decimal  # 0.0 to 1.0, NO FLOAT
    severity: SignalSeverity
    headline: Optional[str]  # Short title
    summary: Optional[str]  # Descriptive text
    payload: dict  # JSON-serializable metadata (bounded)
    tags: list[str] = field(default_factory=list)  # Stable order
    
    def __post_init__(self):
        """Validate invariants on construction"""
        # Confidence must be Decimal in range [0, 1]
        if not isinstance(self.confidence, Decimal):
            raise TypeError(f"confidence must be Decimal, got {type(self.confidence)}")
        if not (Decimal("0") <= self.confidence <= Decimal("1")):
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence}")
        
        # TTL must be positive
        if self.ttl_ms <= 0:
            raise ValueError(f"ttl_ms must be positive, got {self.ttl_ms}")
        
        # Payload must be dict
        if not isinstance(self.payload, dict):
            raise TypeError(f"payload must be dict, got {type(self.payload)}")
        
        # Tags must be list of strings
        if not isinstance(self.tags, list) or not all(isinstance(t, str) for t in self.tags):
            raise TypeError("tags must be list of strings")


@dataclass
class SignalState:
    """
    Runtime state of a signal (mutable for efficient updates).
    
    Separate from SignalEvent to allow state tracking without
    creating new frozen instances.
    """
    signal_id: str
    active: bool
    age_ms: int  # Time since signal creation
    remaining_ms: int  # Time until expiry
    weight: Decimal  # Decay-adjusted weight (0.0 to 1.0)
    reason: Optional[str]  # Why signal was deactivated/expired


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPER FUNCTIONS (PURE, DETERMINISTIC)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def stable_json(obj: dict) -> str:
    """
    Canonical JSON serialization for deterministic hashing.
    
    Rules:
      - Keys sorted alphabetically
      - No whitespace
      - Separators without spaces
    
    Returns:
        Byte-identical JSON string for same input
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def safe_decimal(value: Union[float, int, str, Decimal]) -> Decimal:
    """
    Convert value to Decimal, rejecting float inputs.
    
    Governance Rule G3: NO FLOAT ARITHMETIC
    
    Args:
        value: Numeric value (int, str, or Decimal)
    
    Returns:
        Decimal representation
    
    Raises:
        TypeError: If value is float
        InvalidOperation: If conversion fails
    """
    if isinstance(value, float):
        raise TypeError(f"float not allowed (governance G3), got {value}")
    
    try:
        return Decimal(str(value))
    except InvalidOperation as e:
        raise ValueError(f"Cannot convert {value} to Decimal: {e}")


def derive_signal_id(
    source: SignalSource,
    category: str,
    symbol: Optional[str],
    ts_ms: int,
    headline: Optional[str],
    payload: dict,
) -> str:
    """
    Generate deterministic signal ID via SHA256.
    
    Same inputs → Same ID (reproducible)
    
    Args:
        source: Signal source enum
        category: Signal category string
        symbol: Optional symbol identifier
        ts_ms: Timestamp in milliseconds
        headline: Optional headline text
        payload: Metadata dict
    
    Returns:
        16-character hex digest (first 16 chars of SHA256)
    """
    # Build canonical representation
    canonical = stable_json({
        "source": source.value,
        "category": category,
        "symbol": symbol,
        "ts_ms": ts_ms,
        "headline": headline,
        "payload": payload,
    })
    
    # SHA256 hash → first 16 hex chars
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return digest[:16]


def normalize_symbol(symbol: Optional[str]) -> Optional[str]:
    """
    Normalize symbol to canonical form.
    
    Rules:
      - Uppercase
      - Remove whitespace
      - None passes through
    
    Args:
        symbol: Raw symbol string or None
    
    Returns:
        Normalized symbol or None
    """
    if symbol is None:
        return None
    return symbol.strip().upper()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PUBLIC API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

__all__ = [
    "SignalSource",
    "SignalSeverity",
    "SignalEvent",
    "SignalState",
    "stable_json",
    "safe_decimal",
    "derive_signal_id",
    "normalize_symbol",
]
