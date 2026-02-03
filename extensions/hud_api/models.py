"""
PHASE 13C — HUD API: Models

Deterministic data contracts for dashboard state aggregation.

CRITICAL RULES:
- READ-ONLY (no mutation)
- Fail-safe partial data
- Canonical timestamp normalization
- Stable JSON serialization
"""

import json
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List, Literal


# ────────────────────────────────────────────────────────────────────────────────
# TYPE ALIASES
# ────────────────────────────────────────────────────────────────────────────────

HealthStatus = Literal["UP", "DEGRADED", "DOWN"]


# ────────────────────────────────────────────────────────────────────────────────
# COMPONENT HEALTH
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class ComponentHealth:
    """Health status for a single component."""
    status: HealthStatus
    ts_ms: Optional[int]
    error: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return asdict(self)


# ────────────────────────────────────────────────────────────────────────────────
# SYSTEM HEALTH
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class SystemHealth:
    """Overall system health (multi-component)."""
    supervisor: ComponentHealth
    portfolio: ComponentHealth
    pumps: Dict[str, ComponentHealth]
    audit_api: Optional[ComponentHealth] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "supervisor": self.supervisor.to_dict(),
            "portfolio": self.portfolio.to_dict(),
            "pumps": {symbol: health.to_dict() for symbol, health in self.pumps.items()},
            "audit_api": self.audit_api.to_dict() if self.audit_api else None,
        }


# ────────────────────────────────────────────────────────────────────────────────
# MARKET MINI
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class MarketMini:
    """Minimal market snapshot for UI."""
    symbol: str
    ts_ms: Optional[int] = None
    best_bid: Optional[str] = None
    best_ask: Optional[str] = None
    mid: Optional[str] = None
    trade_price: Optional[str] = None
    is_fresh: Optional[bool] = None
    raw_ref: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return asdict(self)


# ────────────────────────────────────────────────────────────────────────────────
# LOOP MINI
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class LoopMini:
    """Minimal shadow loop status for UI."""
    symbol: str
    status: str
    decision_id: Optional[str] = None
    last_audit_ref: Optional[str] = None
    error: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return asdict(self)


# ────────────────────────────────────────────────────────────────────────────────
# DASHBOARD STATE
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class DashboardState:
    """Top-level unified dashboard state."""
    ts_ms: Optional[int]
    health: SystemHealth
    portfolio: Optional[Dict[str, Any]]
    equity_curve: Optional[Dict[str, Any]]
    market: Dict[str, MarketMini]
    loops: Dict[str, LoopMini]
    alerts: List[Dict[str, Any]]
    stats: Dict[str, int]
    history: List[Dict[str, Any]]
    last_error: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "ts_ms": self.ts_ms,
            "health": self.health.to_dict(),
            "portfolio": self.portfolio,
            "equity_curve": self.equity_curve,
            "market": {symbol: mini.to_dict() for symbol, mini in self.market.items()},
            "loops": {symbol: mini.to_dict() for symbol, mini in self.loops.items()},
            "alerts": self.alerts,
            "stats": self.stats,
            "history": self.history,
            "last_error": self.last_error,
        }


# ────────────────────────────────────────────────────────────────────────────────
# HELPERS
# ────────────────────────────────────────────────────────────────────────────────

def canonical_ts(*candidates: Optional[int]) -> Optional[int]:
    """
    Compute canonical timestamp from candidates (deterministic).
    
    Returns max of all non-None timestamps, or None if all None.
    
    Args:
        *candidates: Timestamp candidates (may be None)
    
    Returns:
        Max timestamp or None
    """
    valid = [ts for ts in candidates if ts is not None]
    return max(valid) if valid else None


def stable_json(obj: Any) -> str:
    """
    Canonical JSON serialization (deterministic).
    
    Args:
        obj: Object to serialize
    
    Returns:
        Canonical JSON string
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))
