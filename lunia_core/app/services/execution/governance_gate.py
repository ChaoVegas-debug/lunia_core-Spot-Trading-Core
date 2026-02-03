"""
EPOCH C: Execution Governance Gate
Authoritative governance re-check at validate / queue / submit / retry
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Literal, Optional

from ...core.state import get_state


@dataclass
class GovernanceDecision:
    """Governance gate decision"""
    decision: Literal["ALLOW", "BLOCK", "ABORT"]
    reason_codes: List[str]
    governance_snapshot: Dict[str, Any]
    metadata: Dict[str, Any]


class ExecutionGovernanceGate:
    """
    Execution Governance Gate
    
    Authoritative governance checks for execution flow.
    Called at: validate, queue, worker pre-submit, retry
    
    Checks (in order):
    1. Global Stop (ABORT if active)
    2. System Mode (BLOCK if STOP)
    3. Run Mode (DRY vs REAL validation)
    4. Airlock Status (ARMED required for REAL)
    5. Market Freshness
    6. Portfolio Freshness
    7. Exchange Health
    """
    
    # Freshness thresholds
    MARKET_FRESHNESS_SEC = 5  # Market data max age
    PORTFOLIO_FRESHNESS_SEC = 10  # Portfolio data max age
    
    def check(
        self,
        run_mode: str,
        market_data: Optional[Dict[str, Any]] = None,
        portfolio: Optional[Dict[str, Any]] = None,
        exchange_health: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> GovernanceDecision:
        """
        Execute governance checks
        
        Args:
            run_mode: "dry" or "real"
            market_data: Market snapshot with timestamp
            portfolio: Portfolio snapshot with timestamp
            exchange_health: Exchange health dict {exchange_id: {status, latency_ms}}
        
        Returns:
            GovernanceDecision (ALLOW / BLOCK / ABORT)
        """
        reason_codes = []
        metadata = {}
        
        # Get runtime state
        state = get_state()
        
        # Capture governance snapshot
        governance_snapshot = {
            "global_stop": state.get("global_stop", False),
            "system_mode": state.get("system_mode", "MANUAL"),
            "run_mode": run_mode,
            "airlock_status": state.get("airlock_status", "NOT_READY"),
            "live_allowed": state.get("live_allowed", False),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # CHECK 1: Global Stop (ABORT)
        if state.get("global_stop", False):
            return GovernanceDecision(
                decision="ABORT",
                reason_codes=["GLOBAL_STOP_ACTIVE"],
                governance_snapshot=governance_snapshot,
                metadata={"abort_reason": "Global stop is active"}
            )
        
        # CHECK 2: System Mode (BLOCK if STOP)
        system_mode = state.get("system_mode", "MANUAL")
        if system_mode == "STOP":
            reason_codes.append("SYSTEM_MODE_STOP")
            return GovernanceDecision(
                decision="BLOCK",
                reason_codes=reason_codes,
                governance_snapshot=governance_snapshot,
                metadata={"system_mode": system_mode}
            )
        
        # CHECK 3: Run Mode Validation
        if run_mode not in ["dry", "real"]:
            reason_codes.append("INVALID_RUN_MODE")
            return GovernanceDecision(
                decision="BLOCK",
                reason_codes=reason_codes,
                governance_snapshot=governance_snapshot,
                metadata={"run_mode": run_mode}
            )
        
        # CHECK 4: Airlock Status (REAL mode only)
        if run_mode == "real":
            airlock_status = state.get("airlock_status", "NOT_READY")
            if airlock_status != "ARMED":
                reason_codes.append("AIRLOCK_NOT_ARMED")
                return GovernanceDecision(
                    decision="BLOCK",
                    reason_codes=reason_codes,
                    governance_snapshot=governance_snapshot,
                    metadata={"airlock_status": airlock_status}
                )
            
            # live_allowed must be true for REAL
            if not state.get("live_allowed", False):
                reason_codes.append("LIVE_NOT_ALLOWED")
                return GovernanceDecision(
                    decision="BLOCK",
                    reason_codes=reason_codes,
                    governance_snapshot=governance_snapshot,
                    metadata={"live_allowed": False}
                )
        
        # CHECK 5: Market Freshness (REAL mode only)
        if run_mode == "real" and market_data:
            market_ts = market_data.get("timestamp")
            if market_ts:
                try:
                    if market_ts.endswith('Z'):
                        market_dt = datetime.fromisoformat(market_ts.replace('Z', '+00:00'))
                    else:
                        market_dt = datetime.fromisoformat(market_ts)
                    
                    age_sec = (datetime.now(timezone.utc) - market_dt).total_seconds()
                    if age_sec > self.MARKET_FRESHNESS_SEC:
                        reason_codes.append("MARKET_DATA_STALE")
                        metadata["market_age_sec"] = age_sec
                        return GovernanceDecision(
                            decision="BLOCK",
                            reason_codes=reason_codes,
                            governance_snapshot=governance_snapshot,
                            metadata=metadata
                        )
                except (ValueError, TypeError):
                    reason_codes.append("MARKET_TIMESTAMP_INVALID")
                    return GovernanceDecision(
                        decision="BLOCK",
                        reason_codes=reason_codes,
                        governance_snapshot=governance_snapshot,
                        metadata=metadata
                    )
        
        # CHECK 6: Portfolio Freshness (REAL mode only)
        if run_mode == "real" and portfolio:
            portfolio_ts = portfolio.get("timestamp")
            if portfolio_ts:
                try:
                    if portfolio_ts.endswith('Z'):
                        portfolio_dt = datetime.fromisoformat(portfolio_ts.replace('Z', '+00:00'))
                    else:
                        portfolio_dt = datetime.fromisoformat(portfolio_ts)
                    
                    age_sec = (datetime.now(timezone.utc) - portfolio_dt).total_seconds()
                    if age_sec > self.PORTFOLIO_FRESHNESS_SEC:
                        reason_codes.append("PORTFOLIO_DATA_STALE")
                        metadata["portfolio_age_sec"] = age_sec
                        return GovernanceDecision(
                            decision="BLOCK",
                            reason_codes=reason_codes,
                            governance_snapshot=governance_snapshot,
                            metadata=metadata
                        )
                except (ValueError, TypeError):
                    reason_codes.append("PORTFOLIO_TIMESTAMP_INVALID")
                    return GovernanceDecision(
                        decision="BLOCK",
                        reason_codes=reason_codes,
                        governance_snapshot=governance_snapshot,
                        metadata=metadata
                    )
        
        # CHECK 7: Exchange Health (REAL mode only)
        if run_mode == "real" and exchange_health:
            for exchange_id, health in exchange_health.items():
                if health.get("status") != "OK":
                    reason_codes.append(f"EXCHANGE_UNHEALTHY_{exchange_id.upper()}")
                    metadata[f"{exchange_id}_status"] = health.get("status")
                    return GovernanceDecision(
                        decision="BLOCK",
                        reason_codes=reason_codes,
                        governance_snapshot=governance_snapshot,
                        metadata=metadata
                    )
        
        # All checks passed
        return GovernanceDecision(
            decision="ALLOW",
            reason_codes=[],
            governance_snapshot=governance_snapshot,
            metadata=metadata
        )
