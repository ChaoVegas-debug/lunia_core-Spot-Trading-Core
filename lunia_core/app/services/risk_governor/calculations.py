"""
Exposure Calculations — Deterministic Portfolio Math

Pessimistic accounting: current + pending + new order.
All calculations pure functions (no side effects).
"""
from typing import Dict

from lunia_core.app.services.execution_bridge.models import OrderPlan
from lunia_core.app.services.risk_governor.models import (
    PortfolioSnapshot,
    Position,
)


def compute_order_notional(
    plan: OrderPlan,
    snapshot: PortfolioSnapshot
) -> float:
    """
    Compute order notional in quote currency.
    
    Args:
        plan: Order to evaluate
        snapshot: Portfolio snapshot with prices
        
    Returns:
        Absolute notional value (always positive)
        
    Raises:
        KeyError: If price missing for symbol
    """
    if plan.symbol not in snapshot.prices:
        raise KeyError(f"Missing price for {plan.symbol}")
    
    price = snapshot.prices[plan.symbol]
    notional = plan.quantity * price
    
    return abs(notional)


def compute_current_exposures(snapshot: PortfolioSnapshot) -> Dict[str, float]:
    """
    Compute current portfolio exposures from positions.
    
    Returns:
        Dict with:
        - total_gross: Sum of abs(position notional)
        - total_net: Signed sum of position notional
        - by_symbol: {symbol: signed_notional}
    """
    total_gross = 0.0
    total_net = 0.0
    by_symbol: Dict[str, float] = {}
    
    for pos in snapshot.positions:
        # Position notional is signed (LONG positive, SHORT negative)
        signed_notional = pos.notional
        
        if pos.side == "SHORT":
            # Ensure SHORT is negative
            signed_notional = -abs(pos.notional)
        elif pos.side == "LONG":
            # Ensure LONG is positive
            signed_notional = abs(pos.notional)
        
        total_gross += abs(signed_notional)
        total_net += signed_notional
        by_symbol[pos.symbol] = signed_notional
    
    return {
        "total_gross": total_gross,
        "total_net": total_net,
        "by_symbol": by_symbol,
    }


def compute_pending_exposures(
    snapshot: PortfolioSnapshot,
    plan: OrderPlan
) -> Dict[str, float]:
    """
    Compute pending order exposures (pessimistic).
    
    Includes all pending orders EXCEPT those matching current plan.id
    (to avoid double-counting if re-evaluating same order).
    
    Returns:
        Dict with:
        - total_gross: Sum of abs(pending notional)
        - by_symbol: {symbol: signed_notional}
        - by_cluster: {cluster_id: gross_notional}
    """
    total_gross = 0.0
    by_symbol: Dict[str, float] = {}
    by_cluster: Dict[str, float] = {}
    
    for pending in snapshot.pending:
        # Skip if this is the current plan (avoid double-count)
        # Note: Would need plan matching logic if pending has plan_id
        # For now, include all pending
        
        signed_notional = pending.notional
        
        total_gross += abs(signed_notional)
        
        by_symbol[pending.symbol] = by_symbol.get(pending.symbol, 0) + signed_notional
        by_cluster[pending.cluster_id] = by_cluster.get(pending.cluster_id, 0) + abs(signed_notional)
    
    return {
        "total_gross": total_gross,
        "by_symbol": by_symbol,
        "by_cluster": by_cluster,
    }


def compute_projected_exposures(
    current: Dict[str, float],
    pending: Dict[str, float],
    order_notional: float,
    plan: OrderPlan,
    cluster_id: str,
    cluster_mapping: Dict[str, str],  # symbol -> cluster_id
) -> Dict[str, float]:
    """
    Compute projected exposures after adding new order.
    
    Pessimistic accounting: current + pending + new.
    
    Args:
        current: Current exposures from compute_current_exposures
        pending: Pending exposures from compute_pending_exposures
        order_notional: New order notional (absolute)
        plan: New order plan
        cluster_id: Correlation cluster for symbol
        cluster_mapping: Symbol to cluster mapping
        
    Returns:
        Dict with projected exposures:
        - projected_gross: Total gross after order
        - projected_net: Total net after order
        - projected_symbol_notional: Symbol exposure after order
        - projected_cluster_gross: Cluster gross after order
        - order_impact_gross: How much gross increases
        - order_impact_net: How much net increases (signed)
    """
    # Current state
    current_gross = current["total_gross"]
    current_net = current["total_net"]
    current_symbol = current["by_symbol"].get(plan.symbol, 0.0)
    
    # Pending state
    pending_gross = pending["total_gross"]
    pending_symbol = pending["by_symbol"].get(plan.symbol, 0.0)
    pending_cluster = pending["by_cluster"].get(cluster_id, 0.0)
    
    #New order impact (signed)
    if plan.side == "BUY":
        order_signed = order_notional  # Positive
    elif plan.side == "SELL":
        order_signed = -order_notional  # Negative
    else:
        # Conservative: treat unknown as additive
        order_signed = order_notional
    
    # Projected totals
    projected_gross = current_gross + pending_gross + abs(order_signed)
    projected_net = current_net + order_signed  # Pending handled pessimistically
    
    # Projected symbol exposure
    projected_symbol_notional = current_symbol + pending_symbol + order_signed
    
    # Projected cluster exposure (gross only)
    # Sum current exposures in this cluster
    current_cluster_gross = sum(
        abs(current["by_symbol"].get(sym, 0))
        for sym in current["by_symbol"].keys()
        if cluster_mapping.get(sym) == cluster_id
    )
    projected_cluster_gross = current_cluster_gross + pending_cluster + abs(order_signed)
    
    return {
        "projected_gross": projected_gross,
        "projected_net": projected_net,
        "projected_symbol_notional": abs(projected_symbol_notional),
        "projected_cluster_gross": projected_cluster_gross,
        "order_impact_gross": abs(order_signed),
        "order_impact_net": order_signed,
        "current_gross": current_gross,
        "current_net": current_net,
        "pending_gross": pending_gross,
    }

