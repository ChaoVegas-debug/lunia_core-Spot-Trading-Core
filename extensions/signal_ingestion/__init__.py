"""
PHASE 15A — SIGNAL INGESTION CORE: Public API

READ-ONLY context layer for external market signals.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  GOVERNANCE WARNING  ⚠️
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This module provides READ-ONLY context for intelligence layers.
It MUST NOT be imported by execution/write modules:

FORBIDDEN IMPORTS:
  ❌ extensions/execution_gateway/
  ❌ extensions/execution_router/
  ❌ extensions/exchange_connectivity/
  ❌ extensions/execution_monitoring/
  ❌ extensions/execution_settlement/

Violation of this module graph invariant will cause CI build failure.

This layer has ZERO trading authority:
  - Cannot create orders
  - Cannot cancel orders
  - Cannot influence execution paths
  - Provides context ONLY for decision-making layers

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Usage:
    from extensions.signal_ingestion import SignalStore, parse_news_signal
    
    store = SignalStore(max_capacity=500)
    
    news_data = {
        "category": "REGULATION",
        "headline": "SEC approves Bitcoin ETF",
        "symbol": "BTC",
        "confidence": "0.95",
        "severity": "HIGH",
        "ttl_ms": 3600000,  # 1 hour
    }
    
    signal = parse_news_signal(news_data, ts_ms=current_time_ms)
    store.upsert(signal)
    
    active = store.list_active(now_ms=current_time_ms)
"""

from .models import (
    SignalEvent,
    SignalSource,
    SignalSeverity,
    SignalState,
    derive_signal_id,
    normalize_symbol,
    safe_decimal,
    stable_json,
)

from .decay import (
    DecayMode,
    compute_decay_weight,
    is_expired,
    remaining_time_ms,
)

from .store import SignalStore

from .ingestors import (
    parse_news_signal,
    parse_whale_signal,
    parse_onchain_signal,
)

__version__ = "0.1.0-alpha"

__all__ = [
    # Models
    "SignalEvent",
    "SignalSource",
    "SignalSeverity",
    "SignalState",
    "derive_signal_id",
    "normalize_symbol",
    "safe_decimal",
    "stable_json",
    # Decay
    "DecayMode",
    "compute_decay_weight",
    "is_expired",
    "remaining_time_ms",
    # Store
    "SignalStore",
    # Ingestors
    "parse_news_signal",
    "parse_whale_signal",
    "parse_onchain_signal",
]
