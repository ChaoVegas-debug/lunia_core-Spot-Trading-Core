"""
PHASE 9.3 — PAPER TYPES

Frozen dataclasses for paper execution: fills, positions, and trade outcomes.

All types are immutable (frozen=True) and use deterministic IDs.
"""

from dataclasses import dataclass
from typing import Optional
from extensions.sandbox.serialization import canonical_hash


@dataclass(frozen=True)
class PaperFill:
    """
    Immutable record of a simulated fill.
    
    Captures all execution costs at fill time.
    """
    side: str  # "buy" | "sell"
    symbol: str
    qty: float
    price: float  # Actual fill price (after worst-side + slippage)
    ts_ms: int
    
    # Cost breakdown
    fee: float
    spread_cost: float
    slippage_cost: float
    latency_cost: float
    
    # Traceability
    intent_id: str
    correlation_id: str
    run_id: str


@dataclass(frozen=True)
class PaperPosition:
    """
    Immutable snapshot of an open paper position.
    
    Created on ENTRY, destroyed on EXIT (replaced with TradeOutcome).
    """
    symbol: str
    side: str  # "long" | "short" (MVP: long-only, but keep field for future)
    qty: float
    avg_entry_price: float
    open_ts_ms: int
    
    # Traceability
    entry_intent_id: str
    run_id: str
    correlation_id: str
    strategy_id: str
    
    # Exit plan (for TTL enforcement)
    time_limit_ms: Optional[int] = None


@dataclass(frozen=True)
class TradeOutcome:
    """
    Immutable record of a completed trade (ENTRY → EXIT).
    
    Captures full P&L breakdown with all costs explicit.
    
    INVARIANT: net_pnl = gross_pnl - (fee_total + spread_total + slippage_total + latency_total)
    """
    outcome_id: str  # Deterministic 16-char hex from canonical_hash
    
    # Trade details
    symbol: str
    side: str  # "long" | "short"
    qty: float
    
    # Timing
    entry_ts_ms: int
    exit_ts_ms: int
    holding_time_ms: int
    
    # Prices
    entry_price: float
    exit_price: float
    
    # P&L breakdown
    gross_pnl: float  # (exit_price - entry_price) * qty for long
    fee_total: float
    spread_total: float
    slippage_total: float
    latency_total: float
    net_pnl: float  # gross - all costs
    
    # Exit classification
    exit_reason: str  # "SIGNAL" | "TTL" | "STOP_LOSS" | "TAKE_PROFIT" | "GOV_FORCE" | "ERROR_SAFE_EXIT"
    
    # Traceability
    entry_intent_id: str
    exit_intent_id: str
    entry_run_id: str
    exit_run_id: str
    entry_correlation_id: str
    exit_correlation_id: str
    strategy_id: str


def create_trade_outcome(
    symbol: str,
    side: str,
    qty: float,
    entry_ts_ms: int,
    exit_ts_ms: int,
    entry_price: float,
    exit_price: float,
    fee_total: float,
    spread_total: float,
    slippage_total: float,
    latency_total: float,
    exit_reason: str,
    entry_intent_id: str,
    exit_intent_id: str,
    entry_run_id: str,
    exit_run_id: str,
    entry_correlation_id: str,
    exit_correlation_id: str,
    strategy_id: str,
) -> TradeOutcome:
    """
    Create TradeOutcome with deterministic outcome_id.
    
    GUARANTEE: Same inputs => same outcome_id (replay-safe).
    """
    holding_time_ms = exit_ts_ms - entry_ts_ms
    
    # Compute P&L (long-only MVP; for short, invert)
    if side == "long":
        gross_pnl = (exit_price - entry_price) * qty
    elif side == "short":
        gross_pnl = (entry_price - exit_price) * qty
    else:
        raise ValueError(f"Unknown side: {side}")
    
    net_pnl = gross_pnl - (fee_total + spread_total + slippage_total + latency_total)
    
    # Generate deterministic outcome_id from core fields
    core_fields = {
        "symbol": symbol,
        "side": side,
        "qty": qty,
        "entry_ts_ms": entry_ts_ms,
        "exit_ts_ms": exit_ts_ms,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "entry_intent_id": entry_intent_id,
        "exit_intent_id": exit_intent_id,
        "strategy_id": strategy_id,
    }
    outcome_id = canonical_hash(core_fields)[:16]  # 16-char hex
    
    return TradeOutcome(
        outcome_id=outcome_id,
        symbol=symbol,
        side=side,
        qty=qty,
        entry_ts_ms=entry_ts_ms,
        exit_ts_ms=exit_ts_ms,
        holding_time_ms=holding_time_ms,
        entry_price=entry_price,
        exit_price=exit_price,
        gross_pnl=gross_pnl,
        fee_total=fee_total,
        spread_total=spread_total,
        slippage_total=slippage_total,
        latency_total=latency_total,
        net_pnl=net_pnl,
        exit_reason=exit_reason,
        entry_intent_id=entry_intent_id,
        exit_intent_id=exit_intent_id,
        entry_run_id=entry_run_id,
        exit_run_id=exit_run_id,
        entry_correlation_id=entry_correlation_id,
        exit_correlation_id=exit_correlation_id,
        strategy_id=strategy_id,
    )
