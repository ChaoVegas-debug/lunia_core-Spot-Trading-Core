"""
EPOCH C: Execution Snapshot Capture
Immutable snapshots at validate / queue / submit
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def capture_execution_snapshot(
    run_mode: str,
    governance_snapshot: Dict[str, Any],
    market_data: Optional[Dict[str, Any]] = None,
    portfolio: Optional[Dict[str, Any]] = None,
    exchange_health: Optional[Dict[str, Dict[str, Any]]] = None,
    guard_results: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Capture execution snapshot
    
    Args:
        run_mode: "dry" or "real"
        governance_snapshot: From governance gate
        market_data: Market snapshot with timestamp
        portfolio: Portfolio snapshot with timestamp
        exchange_health: Exchange health summary
        guard_results: List of guard check results
    
    Returns:
        Immutable execution snapshot
    """
    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_mode": run_mode,
        "governance": governance_snapshot,
        "market_freshness": None,
        "portfolio_freshness": None,
        "exchange_health": exchange_health or {},
        "guard_results": guard_results or []
    }
    
    # Market freshness
    if market_data:
        market_ts = market_data.get("timestamp")
        if market_ts:
            try:
                if market_ts.endswith('Z'):
                    market_dt = datetime.fromisoformat(market_ts.replace('Z', '+00:00'))
                else:
                    market_dt = datetime.fromisoformat(market_ts)
                
                age_sec = (datetime.now(timezone.utc) - market_dt).total_seconds()
                snapshot["market_freshness"] = {
                    "timestamp": market_ts,
                    "age_sec": age_sec,
                    "is_fresh": age_sec <= 5.0
                }
            except (ValueError, TypeError):
                snapshot["market_freshness"] = {
                    "timestamp": market_ts,
                    "age_sec": None,
                    "is_fresh": False,
                    "error": "invalid_timestamp"
                }
    
    # Portfolio freshness
    if portfolio:
        portfolio_ts = portfolio.get("timestamp")
        if portfolio_ts:
            try:
                if portfolio_ts.endswith('Z'):
                    portfolio_dt = datetime.fromisoformat(portfolio_ts.replace('Z', '+00:00'))
                else:
                    portfolio_dt = datetime.fromisoformat(portfolio_ts)
                
                age_sec = (datetime.now(timezone.utc) - portfolio_dt).total_seconds()
                snapshot["portfolio_freshness"] = {
                    "timestamp": portfolio_ts,
                    "age_sec": age_sec,
                    "is_fresh": age_sec <= 10.0
                }
            except (ValueError, TypeError):
                snapshot["portfolio_freshness"] = {
                    "timestamp": portfolio_ts,
                    "age_sec": None,
                    "is_fresh": False,
                    "error": "invalid_timestamp"
                }
    
    return snapshot


def validate_snapshot_completeness(
    snapshot: Dict[str, Any],
    run_mode: str
) -> tuple[bool, List[str]]:
    """
    Validate snapshot completeness (fail-closed in REAL)
    
    Args:
        snapshot: Execution snapshot
        run_mode: "dry" or "real"
    
    Returns:
        (is_complete, missing_fields)
    """
    missing = []
    
    # Required fields (all modes)
    if not snapshot.get("timestamp"):
        missing.append("timestamp")
    
    if not snapshot.get("governance"):
        missing.append("governance")
    
    # REAL mode requirements
    if run_mode == "real":
        if not snapshot.get("market_freshness"):
            missing.append("market_freshness")
        elif not snapshot["market_freshness"].get("is_fresh"):
            missing.append("market_freshness.is_fresh")
        
        if not snapshot.get("portfolio_freshness"):
            missing.append("portfolio_freshness")
        elif not snapshot["portfolio_freshness"].get("is_fresh"):
            missing.append("portfolio_freshness.is_fresh")
        
        if not snapshot.get("exchange_health"):
            missing.append("exchange_health")
    
    return (len(missing) == 0, missing)
