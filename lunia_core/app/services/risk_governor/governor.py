"""
Position & Exposure Governor — Portfolio Safety Enforcer

Pre-execution risk enforcement with fail-closed philosophy.
All decisions deterministic based on portfolio snapshot + limits.
"""
import logging
from typing import List

from lunia_core.app.services.council.models import CouncilVerdict
from lunia_core.app.services.execution_bridge.models import OrderPlan
from lunia_core.app.services.risk_governor.calculations import (
    compute_current_exposures,
    compute_order_notional,
    compute_pending_exposures,
    compute_projected_exposures,
)
from lunia_core.app.services.risk_governor.config import RiskLimits
from lunia_core.app.services.risk_governor.models import (
    Decision,
    GovernorDecision,
    PortfolioSnapshot,
    ReasonCode,
)
from lunia_core.app.services.risk_governor.window_store import (
    CircuitBreakerState,
    WindowCounterStore,
)

logger = logging.getLogger(__name__)


class PositionExposureGovernor:
    """
    Portfolio safety enforcer with pre-execution risk checks.
    
    Evaluates order plans against:
    - Data availability (fail-closed on missing data)
    - Hard limits (BLOCK)
    - Soft limits (MANUAL_REVIEW or DOWNGRADE)
    - Rate limits (thrashing prevention)
    - Circuit breaker (halt recommendation)
    
    All decisions are deterministic and immutable.
    """
    
    def __init__(
        self,
        window_store: WindowCounterStore,
        circuit_breaker: CircuitBreakerState,
    ):
        self.window_store = window_store
        self.circuit_breaker = circuit_breaker
    
    def evaluate(
        self,
        verdict: CouncilVerdict,
        plan: OrderPlan,
        snapshot: PortfolioSnapshot,
        adapter_name: str,
        now_ms: int,
        limits: RiskLimits,
    ) -> GovernorDecision:
        """
        Evaluate order plan against portfolio limits.
        
        Args:
            verdict: Council verdict (for traceability)
            plan: Order plan to evaluate
            snapshot: Portfolio snapshot
            adapter_name: Exchange adapter name
            now_ms: Current timestamp (injected clock)
            limits: Risk limits configuration
            
        Returns:
            GovernorDecision with enforcement action
        """
        reason_codes: List[ReasonCode] = []
        audit: dict = {}
        cluster_id = limits.get_cluster_id(plan.symbol)
        
        try:
            # ================================================================
            # PHASE 1: DATA AVAILABILITY (FAIL-CLOSED)
            # ================================================================
            
            # Check snapshot exists
            if snapshot is None:
                return self._make_block_decision(
                    verdict=verdict,
                    plan=plan,
                    reason_codes=[ReasonCode.MISSING_PORTFOLIO_SNAPSHOT],
                    reasoning="Portfolio snapshot unavailable (fail-closed)",
                    audit={},
                    limits=limits,
                    cluster_id=cluster_id,
                    now_ms=now_ms,
                    adapter_name=adapter_name,
                )
            
            # Check price available
            if plan.symbol not in snapshot.prices:
                return self._make_block_decision(
                    verdict=verdict,
                    plan=plan,
                    reason_codes=[ReasonCode.MISSING_PRICE],
                    reasoning=f"Price missing for {plan.symbol} (fail-closed)",
                    audit={"snapshot_as_of_ms": snapshot.as_of_ms},
                    limits=limits,
                    cluster_id=cluster_id,
                    now_ms=now_ms,
                    adapter_name=adapter_name,
                )
            
            # Check snapshot staleness
            age_ms = now_ms - snapshot.as_of_ms
            if age_ms > limits.snapshot_max_age_ms:
                return self._make_block_decision(
                    verdict=verdict,
                    plan=plan,
                    reason_codes=[ReasonCode.DATA_STALE],
                    reasoning=f"Snapshot stale ({age_ms}ms > {limits.snapshot_max_age_ms}ms)",
                    audit={"age_ms": age_ms, "max_age_ms": limits.snapshot_max_age_ms},
                    limits=limits,
                    cluster_id=cluster_id,
                    now_ms=now_ms,
                    adapter_name=adapter_name,
                )
            
            # ================================================================
            # PHASE 2: EXPOSURE CALCULATIONS
            # ================================================================
            
            order_notional = compute_order_notional(plan, snapshot)
            current = compute_current_exposures(snapshot)
            pending = compute_pending_exposures(snapshot, plan)
            projected = compute_projected_exposures(
                current=current,
                pending=pending,
                order_notional=order_notional,
                plan=plan,
                cluster_id=cluster_id,
                cluster_mapping=limits.correlation_clusters,
            )
            
            audit = {
                "order_notional": order_notional,
                "equity": snapshot.total_equity,
                "current_gross": current["total_gross"],
                "current_net": current["total_net"],
                "pending_gross": pending["total_gross"],
                "projected_gross": projected["projected_gross"],
                "projected_net": projected["projected_net"],
                "projected_symbol_notional": projected["projected_symbol_notional"],
                "projected_cluster_gross": projected["projected_cluster_gross"],
                "cluster_id": cluster_id,
            }
            
            # ================================================================
            # EARLY EXIT: Shadow Mode (LOG_ONLY)
            # ================================================================
            
            if limits.shadow_mode:
                return self._make_decision(
                    verdict=verdict,
                    plan=plan,
                    decision=Decision.LOG_ONLY,
                    reason_codes=[],
                    reasoning="Shadow mode: Allow + journal",
                    audit=audit,
                    limits=limits,
                    cluster_id=cluster_id,
                    window_count=0,
                    consecutive_blocks=0,
                    halt_recommended=False,
                )
            
            # ================================================================
            # PHASE 3: HARD LIMIT CHECKS (BLOCK)
            # ================================================================
            
            # Check order notional cap
            max_order = limits.max_order_notional_pct_of_equity * snapshot.total_equity
            if order_notional > max_order:
                reason_codes.append(ReasonCode.ORDER_NOTIONAL_TOO_LARGE)
                audit["max_order_notional"] = max_order
            
            # Check symbol position cap
            max_position = limits.max_position_notional_pct_of_equity * snapshot.total_equity
            if projected["projected_symbol_notional"] > max_position:
                reason_codes.append(ReasonCode.SYMBOL_POSITION_CAP_EXCEEDED)
                audit["max_position_notional"] = max_position
            
            # Check gross exposure cap
            max_gross = limits.max_total_gross_exposure_pct_of_equity * snapshot.total_equity
            if projected["projected_gross"] > max_gross:
                reason_codes.append(ReasonCode.GROSS_EXPOSURE_CAP_EXCEEDED)
                audit["max_gross_exposure"] = max_gross
            
            # Check net exposure cap
            max_net = limits.max_total_net_exposure_pct_of_equity * snapshot.total_equity
            if abs(projected["projected_net"]) > max_net:
                reason_codes.append(ReasonCode.NET_EXPOSURE_CAP_EXCEEDED)
                audit["max_net_exposure"] = max_net
            
            # Check cluster exposure cap
            max_cluster = limits.max_cluster_gross_exposure_pct_of_equity * snapshot.total_equity
            if projected["projected_cluster_gross"] > max_cluster:
                reason_codes.append(ReasonCode.CLUSTER_EXPOSURE_CAP_EXCEEDED)
                audit["max_cluster_exposure"] = max_cluster
            
            # Check rate limits (orders per hour)
            window_key = f"{adapter_name}:{plan.symbol}"
            window_ms = 3600000  # 1 hour
            window_count = self.window_store.count_last_ms(window_key, now_ms, window_ms)
            
            # Increment counter (optimistic - count this order)
            self.window_store.increment(window_key, now_ms)
            new_window_count = window_count + 1
            
            if new_window_count > limits.max_symbol_orders_per_hour:
                reason_codes.append(ReasonCode.ORDER_RATE_LOOP)
                audit["window_count_orders_hour"] = new_window_count
                audit["max_orders_per_hour"] = limits.max_symbol_orders_per_hour
            
            # ================================================================
            # PHASE 4: SOFT LIMIT CHECKS (WARN)
            # ================================================================
            
            soft_violations: List[ReasonCode] = []
            
            # Soft: order notional
            warn_order = limits.warn_order_notional_pct_of_equity * snapshot.total_equity
            if order_notional > warn_order:
                soft_violations.append(ReasonCode.SOFT_WARN_SYMBOL_CONCENTRATION)
                audit["warn_order_notional"] = warn_order
            
            # Soft: gross exposure
            warn_gross = limits.warn_total_gross_exposure_pct_of_equity * snapshot.total_equity
            if projected["projected_gross"] > warn_gross:
                soft_violations.append(ReasonCode.SOFT_WARN_GROSS_EXPOSURE)
                audit["warn_gross_exposure"] = warn_gross
            
            # Soft: cluster exposure
            warn_cluster = limits.warn_cluster_gross_exposure_pct_of_equity * snapshot.total_equity
            if projected["projected_cluster_gross"] > warn_cluster:
                soft_violations.append(ReasonCode.SOFT_WARN_CLUSTER_EXPOSURE)
                audit["warn_cluster_exposure"] = warn_cluster
            
            # ================================================================
            # PHASE 5: CIRCUIT BREAKER CHECK
            # ================================================================
            
            consecutive_blocks = self.circuit_breaker.get_count(adapter_name, plan.symbol)
            halt_recommended = False
            
            if reason_codes:
                # About to block - increment circuit breaker
                consecutive_blocks = self.circuit_breaker.record_block(adapter_name, plan.symbol)
                
                if consecutive_blocks >= limits.circuit_breaker_consecutive_blocks:
                    reason_codes.append(ReasonCode.CIRCUIT_BREAKER_TRIPPED)
                    halt_recommended = True
                    audit["consecutive_blocks"] = consecutive_blocks
                    audit["circuit_breaker_threshold"] = limits.circuit_breaker_consecutive_blocks
            else:
                # Passing checks - reset circuit breaker
                self.circuit_breaker.reset(adapter_name, plan.symbol)
                consecutive_blocks = 0
            
            # ================================================================
            # PHASE 6: DECISION LOGIC
            # ================================================================
            
            # Hard violations → BLOCK
            if reason_codes:
                return self._make_decision(
                    verdict=verdict,
                    plan=plan,
                    decision=Decision.BLOCK,
                    reason_codes=reason_codes,
                    reasoning=self._format_reasoning(reason_codes, audit),
                    audit=audit,
                    limits=limits,
                    cluster_id=cluster_id,
                    window_count=new_window_count,
                    consecutive_blocks=consecutive_blocks,
                    halt_recommended=halt_recommended,
                )
            
            # Soft violations → MANUAL_REVIEW or DOWNGRADE
            if soft_violations:
                if limits.soft_action == "DOWNGRADE_TO_DRY_RUN":
                    decision = Decision.DOWNGRADE_TO_DRY_RUN
                else:
                    decision = Decision.REQUIRES_MANUAL_REVIEW
                
                return self._make_decision(
                    verdict=verdict,
                    plan=plan,
                    decision=decision,
                    reason_codes=soft_violations,
                    reasoning=self._format_reasoning(soft_violations, audit),
                    audit=audit,
                    limits=limits,
                    cluster_id=cluster_id,
                    window_count=new_window_count,
                    consecutive_blocks=consecutive_blocks,
                    halt_recommended=False,
                )
            
            # Clean pass → ALLOW
            return self._make_decision(
                verdict=verdict,
                plan=plan,
                decision=Decision.ALLOW,
                reason_codes=[],
                reasoning="All limits passed",
                audit=audit,
                limits=limits,
                cluster_id=cluster_id,
                window_count=new_window_count,
                consecutive_blocks=consecutive_blocks,
                halt_recommended=False,
            )
        
        except Exception as e:
            # FAIL-CLOSED: Internal error → BLOCK
            logger.error(
                f"Governor internal error for plan {plan.id}: {e}",
                exc_info=True,
            )
            
            return self._make_block_decision(
                verdict=verdict,
                plan=plan,
                reason_codes=[ReasonCode.INTERNAL_ERROR_FAIL_CLOSED],
                reasoning=f"Internal error (fail-closed): {str(e)[:200]}",
                audit={"error": str(e)[:500]},
                limits=limits,
                cluster_id=cluster_id,
                now_ms=now_ms,
                adapter_name=adapter_name,
            )
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _make_decision(
        self,
        verdict: CouncilVerdict,
        plan: OrderPlan,
        decision: Decision,
        reason_codes: List[ReasonCode],
        reasoning: str,
        audit: dict,
        limits: RiskLimits,
        cluster_id: str,
        window_count: int,
        consecutive_blocks: int,
        halt_recommended: bool,
    ) -> GovernorDecision:
        """Create a GovernorDecision"""
        return GovernorDecision(
            verdict_id=verdict.id,
            plan_id=plan.id,
            decision=decision,
            reason_codes=reason_codes,
            reasoning=reasoning,
            audit=audit,
            limits_snapshot=limits.to_snapshot_dict(),
            correlation_cluster_id=cluster_id,
            window_count_orders_hour=window_count,
            consecutive_blocks=consecutive_blocks,
            halt_recommended=halt_recommended,
        )
    
    def _make_block_decision(
        self,
        verdict: CouncilVerdict,
        plan: OrderPlan,
        reason_codes: List[ReasonCode],
        reasoning: str,
        audit: dict,
        limits: RiskLimits,
        cluster_id: str,
        now_ms: int,
        adapter_name: str,
    ) -> GovernorDecision:
        """Create a BLOCK decision (for fail-closed cases)"""
        # Increment circuit breaker
        consecutive_blocks = self.circuit_breaker.record_block(adapter_name, plan.symbol)
        halt_recommended = consecutive_blocks >= limits.circuit_breaker_consecutive_blocks
        
        return GovernorDecision(
            verdict_id=verdict.id,
            plan_id=plan.id,
            decision=Decision.BLOCK,
            reason_codes=reason_codes,
            reasoning=reasoning,
            audit=audit,
            limits_snapshot=limits.to_snapshot_dict(),
            correlation_cluster_id=cluster_id,
            window_count_orders_hour=None,
            consecutive_blocks=consecutive_blocks,
            halt_recommended=halt_recommended,
        )
    
    def _format_reasoning(
        self,
        reason_codes: List[ReasonCode],
        audit: dict,
    ) -> str:
        """Format human-readable reasoning"""
        if not reason_codes:
            return "All limits passed"
        
        parts = []
        for code in reason_codes:
            if code == ReasonCode.ORDER_NOTIONAL_TOO_LARGE:
                parts.append(
                    f"Order notional ${audit.get('order_notional', 0):.2f} "
                    f"> ${audit.get('max_order_notional', 0):.2f}"
                )
            elif code == ReasonCode.SYMBOL_POSITION_CAP_EXCEEDED:
                parts.append(
                    f"Symbol position ${audit.get('projected_symbol_notional', 0):.2f} "
                    f"> ${audit.get('max_position_notional', 0):.2f}"
                )
            elif code == ReasonCode.GROSS_EXPOSURE_CAP_EXCEEDED:
                parts.append(
                    f"Gross exposure ${audit.get('projected_gross', 0):.2f} "
                    f"> ${audit.get('max_gross_exposure', 0):.2f}"
                )
            elif code == ReasonCode.NET_EXPOSURE_CAP_EXCEEDED:
                parts.append(
                    f"Net exposure ${abs(audit.get('projected_net', 0)):.2f} "
                    f"> ${audit.get('max_net_exposure', 0):.2f}"
                )
            elif code == ReasonCode.CLUSTER_EXPOSURE_CAP_EXCEEDED:
                parts.append(
                    f"Cluster exposure ${audit.get('projected_cluster_gross', 0):.2f} "
                    f"> ${audit.get('max_cluster_exposure', 0):.2f}"
                )
            elif code == ReasonCode.ORDER_RATE_LOOP:
                parts.append(
                    f"Rate limit: {audit.get('window_count_orders_hour', 0)} orders/hour "
                    f"> {audit.get('max_orders_per_hour', 0)}"
                )
            else:
                parts.append(code.value)
        
        return "; ".join(parts)
