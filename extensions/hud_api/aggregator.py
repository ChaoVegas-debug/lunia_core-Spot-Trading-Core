"""
PHASE 13C — HUD API: Aggregator

READ-ONLY system aggregator for unified dashboard state.

CRITICAL RULES:
- READ-ONLY (only call getters: get_status, get_state, get_latest_snapshot, get_equity_curve)
- Fail-safe (component failures → partial data + DOWN health)
- No wall-clock (timestamps from events only)
- Deterministic (sorted symbols, canonical JSON)
- Bounded memory (ring buffer for history)
"""

from typing import Dict, Any, Optional
from collections import deque

from .models import (
    ComponentHealth, SystemHealth, MarketMini, LoopMini, DashboardState,
    canonical_ts, stable_json
)


class SystemAggregator:
    """
    READ-ONLY aggregator for unified dashboard state.
    
    Features:
    - Multi-component health tracking
    - Fail-safe partial data
    - Deterministic ordering
    - Bounded history
    """
    
    def __init__(
        self,
        supervisor: Any,  # ShadowSupervisor
        portfolio: Any,  # PortfolioManager
        pumps: Dict[str, Any],  # Dict[symbol → LiveDataPump]
        *,
        max_history: int = 100,
        equity_curve_limit: int = 100,
    ):
        """
        Initialize system aggregator.
        
        Args:
            supervisor: ShadowSupervisor instance
            portfolio: PortfolioManager instance
            pumps: Dict of symbol → LiveDataPump
            max_history: Max dashboard history (bounded)
            equity_curve_limit: Max equity curve items to fetch
        """
        self.supervisor = supervisor
        self.portfolio = portfolio
        self.pumps = pumps
        self.equity_curve_limit = equity_curve_limit
        
        # Bounded history ring buffer
        self.history: deque = deque(maxlen=max_history)
        
        # Last error
        self.last_error: Optional[Dict[str, Any]] = None
    
    def _get_supervisor_health(self) -> tuple[ComponentHealth, Optional[Dict[str, Any]]]:
        """
        Get supervisor health and status.
        
        Returns:
            (ComponentHealth, status_dict | None)
        """
        try:
            status = self.supervisor.get_status()
            
            # Extract timestamp (if available)
            ts_ms = status.get("ts_ms")
            
            # Health: UP if status retrieved
            health = ComponentHealth(
                status="UP",
                ts_ms=ts_ms,
                error=None
            )
            
            return health, status
        
        except Exception as e:
            # DOWN on exception
            health = ComponentHealth(
                status="DOWN",
                ts_ms=None,
                error={
                    "code": "SUPERVISOR_ERROR",
                    "message": f"Supervisor get_status failed: {str(e)[:100]}",
                    "details": {"exception": str(e)}
                }
            )
            return health, None
    
    def _get_portfolio_health(self) -> tuple[ComponentHealth, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Get portfolio health, state, and equity curve.
        
        Returns:
            (ComponentHealth, state_dict | None, equity_curve | None)
        """
        try:
            state = self.portfolio.get_state()
            equity_curve = self.portfolio.get_equity_curve(limit=self.equity_curve_limit)
            
            # Convert state to dict
            state_dict = state.to_dict()
            
            # Extract timestamp
            ts_ms = state_dict.get("ts_ms")
            
            # Health: UP if state retrieved
            health = ComponentHealth(
                status="UP",
                ts_ms=ts_ms,
                error=None
            )
            
            return health, state_dict, equity_curve
        
        except Exception as e:
            # DOWN on exception
            health = ComponentHealth(
                status="DOWN",
                ts_ms=None,
                error={
                    "code": "PORTFOLIO_ERROR",
                    "message": f"Portfolio get_state/get_equity_curve failed: {str(e)[:100]}",
                    "details": {"exception": str(e)}
                }
            )
            return health, None, None
    
    def _get_pump_health_and_market(self, symbol: str, pump: Any) -> tuple[ComponentHealth, MarketMini]:
        """
        Get pump health and market mini.
        
        Args:
            symbol: Trading symbol
            pump: LiveDataPump instance
        
        Returns:
            (ComponentHealth, MarketMini)
        """
        try:
            snapshot = pump.get_latest_snapshot()
            
            if not snapshot:
                # DEGRADED: no snapshot available
                health = ComponentHealth(
                    status="DEGRADED",
                    ts_ms=None,
                    error={
                        "code": "NO_SNAPSHOT",
                        "message": "No snapshot available from pump"
                    }
                )
                market = MarketMini(symbol=symbol)
                return health, market
            
            # Extract fields
            ts_ms = snapshot.get("event_ts_ms") or snapshot.get("server_ts_ms")
            
            top = snapshot.get("top", {})
            trade = snapshot.get("trade", {})
            health_obj = snapshot.get("health", {})
            
            best_bid = top.get("best_bid")
            best_ask = top.get("best_ask")
            mid = top.get("mid")
            trade_price = trade.get("price")
            is_fresh = health_obj.get("is_fresh")
            
            # Build market mini
            market = MarketMini(
                symbol=symbol,
                ts_ms=ts_ms,
                best_bid=best_bid,
                best_ask=best_ask,
                mid=mid,
                trade_price=trade_price,
                is_fresh=is_fresh,
                raw_ref=None  # Could add snapshot ID if available
            )
            
            # Health: UP if fresh, DEGRADED if stale
            if is_fresh:
                health = ComponentHealth(status="UP", ts_ms=ts_ms, error=None)
            else:
                health = ComponentHealth(
                    status="DEGRADED",
                    ts_ms=ts_ms,
                    error={
                        "code": "STALE_SNAPSHOT",
                        "message": health_obj.get("stale_reason", "Snapshot is stale")
                    }
                )
            
            return health, market
        
        except Exception as e:
            # DOWN on exception
            health = ComponentHealth(
                status="DOWN",
                ts_ms=None,
                error={
                    "code": "PUMP_ERROR",
                    "message": f"Pump get_latest_snapshot failed: {str(e)[:100]}",
                    "details": {"exception": str(e)}
                }
            )
            market = MarketMini(symbol=symbol)
            return health, market
    
    def _get_loop_minis(self, supervisor_status: Optional[Dict[str, Any]]) -> Dict[str, LoopMini]:
        """
        Extract loop minis from supervisor status.
        
        Args:
            supervisor_status: Supervisor status dict (or None)
        
        Returns:
            Dict[symbol → LoopMini]
        """
        loop_minis = {}
        
        if not supervisor_status:
            # No supervisor status: create minimal placeholders for all pumps
            for symbol in sorted(self.pumps.keys()):
                loop_minis[symbol] = LoopMini(
                    symbol=symbol,
                    status="UNKNOWN",
                    decision_id=None,
                    last_audit_ref=None,
                    error={"code": "NO_STATUS", "message": "Supervisor status unavailable"}
                )
            return loop_minis
        
        # Extract from supervisor status
        loops_dict = supervisor_status.get("loops", {})
        
        for symbol in sorted(self.pumps.keys()):
            loop_data = loops_dict.get(symbol, {})
            
            loop_minis[symbol] = LoopMini(
                symbol=symbol,
                status=loop_data.get("status", "UNKNOWN"),
                decision_id=None,  # Not in supervisor status (would need loop ref)
                last_audit_ref=loop_data.get("last_audit_ref"),
                error=loop_data.get("last_error")
            )
        
        return loop_minis
    
    def _compute_stats(self, supervisor_status: Optional[Dict[str, Any]]) -> Dict[str, int]:
        """
        Compute aggregated stats.
        
        Args:
            supervisor_status: Supervisor status dict (or None)
        
        Returns:
            Stats dict
        """
        if not supervisor_status:
            return {
                "executed": 0,
                "skipped_stale": 0,
                "skipped_noop": 0,
                "errors": 0,
            }
        
        # Aggregate from loops
        loops_dict = supervisor_status.get("loops", {})
        
        executed = 0
        skipped_stale = 0
        skipped_noop = 0
        errors = 0
        
        for loop_data in loops_dict.values():
            executed += loop_data.get("executed_count", 0)
            skipped_stale += loop_data.get("skipped_stale_count", 0)
            skipped_noop += loop_data.get("skipped_noop_count", 0)
            errors += loop_data.get("error_count", 0)
        
        return {
            "executed": executed,
            "skipped_stale": skipped_stale,
            "skipped_noop": skipped_noop,
            "errors": errors,
        }
    
    def get_dashboard(self) -> Dict[str, Any]:
        """
        Get unified dashboard state (READ-ONLY).
        
        Returns:
            DashboardState dict
        """
        try:
            # 1. Get supervisor health & status
            supervisor_health, supervisor_status = self._get_supervisor_health()
            
            # 2. Get portfolio health, state, equity curve
            portfolio_health, portfolio_state, equity_curve = self._get_portfolio_health()
            
            # 3. Get pump health & market minis (deterministic symbol order)
            pump_healths = {}
            market_minis = {}
            
            for symbol in sorted(self.pumps.keys()):
                pump = self.pumps[symbol]
                health, market = self._get_pump_health_and_market(symbol, pump)
                pump_healths[symbol] = health
                market_minis[symbol] = market
            
            # 4. Get loop minis
            loop_minis = self._get_loop_minis(supervisor_status)
            
            # 5. Extract alerts from portfolio state
            alerts = []
            if portfolio_state:
                alerts = portfolio_state.get("alerts", [])
            
            # 6. Compute stats
            stats = self._compute_stats(supervisor_status)
            
            # 7. Compute canonical timestamp (max of all component timestamps)
            ts_candidates = [supervisor_health.ts_ms, portfolio_health.ts_ms]
            ts_candidates.extend([h.ts_ms for h in pump_healths.values()])
            ts_ms = canonical_ts(*ts_candidates)
            
            # 8. Build system health
            system_health = SystemHealth(
                supervisor=supervisor_health,
                portfolio=portfolio_health,
                pumps=pump_healths,
                audit_api=None  # Not wired in 13C
            )
            
            # 9. Build dashboard state
            dashboard = DashboardState(
                ts_ms=ts_ms,
                health=system_health,
                portfolio=portfolio_state,
                equity_curve=equity_curve,
                market=market_minis,
                loops=loop_minis,
                alerts=alerts,
                stats=stats,
                history=list(self.history),  # Copy for safety
                last_error=self.last_error
            )
            
            # 10. Add to history (store simplified version to save memory)
            history_entry = {
                "ts_ms": ts_ms,
                "equity": portfolio_state.get("equity") if portfolio_state else None,
                "stats": stats,
                "health_summary": {
                    "supervisor": supervisor_health.status,
                    "portfolio": portfolio_health.status,
                    "pumps_up_count": sum(1 for h in pump_healths.values() if h.status == "UP")
                }
            }
            self.history.append(history_entry)
            
            # Return as dict
            return dashboard.to_dict()
        
        except Exception as e:
            # Ultimate fail-safe: return minimal valid dashboard
            error = {
                "code": "AGGREGATOR_ERROR",
                "message": f"Dashboard aggregation failed: {str(e)[:200]}",
                "details": {"exception": str(e)}
            }
            self.last_error = error
            
            # Minimal dashboard
            return {
                "ts_ms": None,
                "health": {
                    "supervisor": {"status": "DOWN", "ts_ms": None, "error": error},
                    "portfolio": {"status": "DOWN", "ts_ms": None, "error": error},
                    "pumps": {},
                    "audit_api": None
                },
                "portfolio": None,
                "equity_curve": None,
                "market": {},
                "loops": {},
                "alerts": [],
                "stats": {"executed": 0, "skipped_stale": 0, "skipped_noop": 0, "errors": 0},
                "history": list(self.history),
                "last_error": error
            }
