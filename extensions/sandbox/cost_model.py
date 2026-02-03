"""
PHASE 9.3 — COST MODEL

Deterministic cost functions for paper execution.

GUARANTEE: No randomness. All costs are pure functions of inputs.
All outputs rounded to FLOAT_PRECISION=8 from Phase 9.2.
"""

from extensions.sandbox.serialization import FLOAT_PRECISION
from extensions.protocol.protocol import VolatilityState


def compute_fee(notional: float, fee_rate: float) -> float:
    """
    Compute trading fee.
    
    Args:
        notional: Trade size in quote currency (price * qty)
        fee_rate: Fee rate as decimal (e.g., 0.001 for 0.1%)
        
    Returns:
        Fee amount, rounded to FLOAT_PRECISION
    """
    fee = notional * fee_rate
    return round(fee, FLOAT_PRECISION)


def compute_spread_cost(side: str, bid: float, ask: float, qty: float) -> float:
    """
    Compute spread cost from worst-side execution.
    
    Worst side: BUY at ASK, SELL at BID.
    Spread cost = |mid - execution_price| * qty
    
    Args:
        side: "buy" | "sell"
        bid: Best bid price
        ask: Best ask price
        qty: Trade quantity
        
    Returns:
        Spread cost, rounded to FLOAT_PRECISION
    """
    mid = (bid + ask) / 2.0
    
    if side == "buy":
        execution_price = ask
    elif side == "sell":
        execution_price = bid
    else:
        raise ValueError(f"Unknown side: {side}")
    
    spread_cost = abs(mid - execution_price) * qty
    return round(spread_cost, FLOAT_PRECISION)


def compute_slippage_cost(
    mid: float,
    qty: float,
    volatility_state: VolatilityState,
) -> float:
    """
    Compute deterministic slippage cost.
    
    Rules (basis points):
    - CALM: 1 bp (0.01%)
    - NORMAL: 2 bp (0.02%)
    - ELEVATED: 5 bp (0.05%)
    - EXTREME: 20 bp (0.20%) + quadratic size penalty
    - HALTED: 0 bp (market halted, no slippage but execution likely blocked)
    
    Quadratic size penalty for EXTREME:
    slippage_bps = base_bps + k * (qty^2) where k = 0.0001
    
    Args:
        mid: Mid price
        qty: Trade quantity in base currency
        volatility_state: Market volatility classification
        
    Returns:
        Slippage cost, rounded to FLOAT_PRECISION
    """
    # Base slippage in basis points
    if volatility_state == VolatilityState.CALM:
        slippage_bps = 1.0
    elif volatility_state == VolatilityState.NORMAL:
        slippage_bps = 2.0
    elif volatility_state == VolatilityState.ELEVATED:
        slippage_bps = 5.0
    elif volatility_state == VolatilityState.EXTREME:
        # Base + quadratic size penalty
        base_bps = 20.0
        size_penalty_k = 0.0001
        size_penalty_bps = size_penalty_k * (qty ** 2)
        slippage_bps = base_bps + size_penalty_bps
    elif volatility_state == VolatilityState.HALTED:
        slippage_bps = 0.0  # No slippage (execution blocked anyway)
    else:
        raise ValueError(f"Unknown volatility_state: {volatility_state}")
    
    # Convert bps to decimal
    slippage_rate = slippage_bps / 10000.0
    
    # Cost = rate * notional
    notional = mid * qty
    slippage_cost = notional * slippage_rate
    
    return round(slippage_cost, FLOAT_PRECISION)


def compute_latency_cost(
    mid: float,
    qty: float,
    latency_ms: int,
    latency_bps_per_100ms: float = 0.5,
) -> float:
    """
    Compute deterministic latency cost.
    
    Latency causes adverse price movement between signal and execution.
    
    Rule: cost_bps = latency_bps_per_100ms * (latency_ms / 100)
    
    Args:
        mid: Mid price at signal time
        qty: Trade quantity
        latency_ms: Execution latency in milliseconds
        latency_bps_per_100ms: Basis points of drift per 100ms (default: 0.5 bp)
        
    Returns:
        Latency cost, rounded to FLOAT_PRECISION
    """
    if latency_ms < 0:
        raise ValueError(f"Latency cannot be negative: latency_ms={latency_ms}")
    
    # Compute cost in basis points
    cost_bps = latency_bps_per_100ms * (latency_ms / 100.0)
    
    # Convert to decimal
    cost_rate = cost_bps / 10000.0
    
    # Cost = rate * notional
    notional = mid * qty
    latency_cost = notional * cost_rate
    
    return round(latency_cost, FLOAT_PRECISION)


def compute_fill_price(
    side: str,
    bid: float,
    ask: float,
    mid: float,
    qty: float,
    volatility_state: VolatilityState,
    latency_ms: int,
) -> float:
    """
    Compute actual fill price after all costs.
    
    Fill price = worst_side_price + slippage_impact + latency_impact
    
    Args:
        side: "buy" | "sell"
        bid: Best bid
        ask: Best ask
        mid: Mid price
        qty: Quantity
        volatility_state: Volatility classification
        latency_ms: Execution latency
        
    Returns:
        Actual fill price, rounded to FLOAT_PRECISION
    """
    # Start with worst-side price
    if side == "buy":
        base_price = ask
    elif side == "sell":
        base_price = bid
    else:
        raise ValueError(f"Unknown side: {side}")
    
    # Compute slippage impact (per unit)
    slippage_cost_total = compute_slippage_cost(mid, qty, volatility_state)
    slippage_per_unit = slippage_cost_total / qty if qty > 0 else 0.0
    
    # Compute latency impact (per unit)
    latency_cost_total = compute_latency_cost(mid, qty, latency_ms)
    latency_per_unit = latency_cost_total / qty if qty > 0 else 0.0
    
    # Apply impacts (buy: add costs; sell: subtract costs)
    if side == "buy":
        fill_price = base_price + slippage_per_unit + latency_per_unit
    else:  # sell
        fill_price = base_price - slippage_per_unit - latency_per_unit
    
    return round(fill_price, FLOAT_PRECISION)
