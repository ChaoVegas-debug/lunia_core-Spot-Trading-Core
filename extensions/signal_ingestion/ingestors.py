"""
PHASE 15A — SIGNAL INGESTION CORE: Ingestors

Parsing adapters for external signal sources.
NO network I/O (parsing only), fail-closed on missing fields.

Governance: G4 (Fail-Closed) enforced
"""

from decimal import Decimal
from typing import Any, Optional

from .models import (
    SignalEvent,
    SignalSource,
    SignalSeverity,
    derive_signal_id,
    normalize_symbol,
    safe_decimal,
)


def parse_news_signal(
    data: dict[str, Any],
    ts_ms: int,
) -> SignalEvent:
    """
    Parse NEWS signal from raw data.
    
    Required fields:
      - category: str (e.g., "REGULATION", "MACRO", "BREAKING")
      - headline: str
      - summary: str (optional)
      - symbol: str | None
      - confidence: float | int | str | Decimal (0-1)
      - severity: str ("LOW", "MEDIUM", "HIGH", "CRITICAL")
      - ttl_ms: int
    
    Args:
        data: Raw news signal data (dict)
        ts_ms: Signal timestamp (milliseconds)
    
    Returns:
        SignalEvent
    
    Raises:
        ValueError: If required fields missing or invalid
        TypeError: If confidence is float (forbidden by governance)
    """
    # Fail-closed: require all critical fields
    try:
        category = data["category"]
        headline = data["headline"]
        symbol = normalize_symbol(data.get("symbol"))
        confidence = safe_decimal(data["confidence"])
        severity = SignalSeverity(data["severity"])
        ttl_ms = int(data["ttl_ms"])
    except KeyError as e:
        raise ValueError(f"Missing required field in NEWS signal: {e}")
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid field in NEWS signal: {e}")
    
    # Optional fields with safe defaults
    summary = data.get("summary")
    tags = data.get("tags", [])
    payload = data.get("payload", {})
    
    # Derive deterministic ID
    signal_id = derive_signal_id(
        source=SignalSource.NEWS,
        category=category,
        symbol=symbol,
        ts_ms=ts_ms,
        headline=headline,
        payload=payload,
    )
    
    return SignalEvent(
        signal_id=signal_id,
        source=SignalSource.NEWS,
        category=category,
        symbol=symbol,
        ts_ms=ts_ms,
        ttl_ms=ttl_ms,
        confidence=confidence,
        severity=severity,
        headline=headline,
        summary=summary,
        payload=payload,
        tags=tags,
    )


def parse_whale_signal(
    data: dict[str, Any],
    ts_ms: int,
) -> SignalEvent:
    """
    Parse WHALE signal (large on-chain movements).
    
    Required fields:
      - category: str (e.g., "ACCUMULATION", "DISTRIBUTION", "TRANSFER")
      - symbol: str
      - amount: float | int | str | Decimal
      - confidence: float | int | str | Decimal (0-1)
      - severity: str
      - ttl_ms: int
    
    Args:
        data: Raw whale signal data
        ts_ms: Signal timestamp (milliseconds)
    
    Returns:
        SignalEvent
    
    Raises:
        ValueError: If required fields missing or invalid
    """
    try:
        category = data["category"]
        symbol = normalize_symbol(data["symbol"])
        amount = safe_decimal(data["amount"])
        confidence = safe_decimal(data["confidence"])
        severity = SignalSeverity(data["severity"])
        ttl_ms = int(data["ttl_ms"])
    except KeyError as e:
        raise ValueError(f"Missing required field in WHALE signal: {e}")
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid field in WHALE signal: {e}")
    
    # Build headline from data
    headline = f"{category} {symbol}: {amount}"
    
    # Payload includes full transaction details
    payload = {
        "amount": str(amount),
        "from_address": data.get("from_address"),
        "to_address": data.get("to_address"),
        "tx_hash": data.get("tx_hash"),
        **(data.get("payload", {})),
    }
    
    tags = data.get("tags", [])
    
    signal_id = derive_signal_id(
        source=SignalSource.WHALE,
        category=category,
        symbol=symbol,
        ts_ms=ts_ms,
        headline=headline,
        payload=payload,
    )
    
    return SignalEvent(
        signal_id=signal_id,
        source=SignalSource.WHALE,
        category=category,
        symbol=symbol,
        ts_ms=ts_ms,
        ttl_ms=ttl_ms,
        confidence=confidence,
        severity=severity,
        headline=headline,
        summary=data.get("summary"),
        payload=payload,
        tags=tags,
    )


def parse_onchain_signal(
    data: dict[str, Any],
    ts_ms: int,
) -> SignalEvent:
    """
    Parse ONCHAIN signal (protocol metrics, activity).
    
    Required fields:
      - category: str (e.g., "TVL_CHANGE", "GAS_SPIKE", "WHALE_CLUSTER")
      - symbol: str | None (protocol or asset)
      - metric_value: float | int | str | Decimal
      - confidence: float | int | str | Decimal (0-1)
      - severity: str
      - ttl_ms: int
    
    Args:
        data: Raw onchain signal data
        ts_ms: Signal timestamp (milliseconds)
    
    Returns:
        SignalEvent
    """
    try:
        category = data["category"]
        symbol = normalize_symbol(data.get("symbol"))
        metric_value = safe_decimal(data["metric_value"])
        confidence = safe_decimal(data["confidence"])
        severity = SignalSeverity(data["severity"])
        ttl_ms = int(data["ttl_ms"])
    except KeyError as e:
        raise ValueError(f"Missing required field in ONCHAIN signal: {e}")
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid field in ONCHAIN signal: {e}")
    
    headline = data.get("headline") or f"{category}: {metric_value}"
    
    payload = {
        "metric_value": str(metric_value),
        "metric_name": data.get("metric_name"),
        "chain": data.get("chain"),
        **(data.get("payload", {})),
    }
    
    tags = data.get("tags", [])
    
    signal_id = derive_signal_id(
        source=SignalSource.ONCHAIN,
        category=category,
        symbol=symbol,
        ts_ms=ts_ms,
        headline=headline,
        payload=payload,
    )
    
    return SignalEvent(
        signal_id=signal_id,
        source=SignalSource.ONCHAIN,
        category=category,
        symbol=symbol,
        ts_ms=ts_ms,
        ttl_ms=ttl_ms,
        confidence=confidence,
        severity=severity,
        headline=headline,
        summary=data.get("summary"),
        payload=payload,
        tags=tags,
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PUBLIC API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

__all__ = [
    "parse_news_signal",
    "parse_whale_signal",
    "parse_onchain_signal",
]
