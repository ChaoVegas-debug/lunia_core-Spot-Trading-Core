"""
Governed Order Executor — Portfolio-Safe Execution Wrapper

Wraps OrderExecutor with pre-execution risk governance.
ADDITIVE ONLY — No modifications to locked executor/planner.
"""
import logging
from typing import Protocol

from lunia_core.app.services.council.models import CouncilVerdict
from lunia_core.app.services.execution_bridge.executor import OrderExecutor
from lunia_core.app.services.execution_bridge.models import ExecutionResult, OrderPlan
from lunia_core.app.services.execution_bridge.planner import OrderPlanner
from lunia_core.app.services.risk_governor.config import RiskLimits
from lunia_core.app.services.risk_governor.governor import PositionExposureGovernor
from lunia_core.app.services.risk_governor.journal import (
    RiskGovernorEvent,
    RiskGovernorJournal,
)
from lunia_core.app.services.risk_governor.models import (
    Decision,
    PortfolioSnapshot,
)
from lunia_core.app.services.risk_governor.window_store import (
    CircuitBreakerState,
    WindowCounterStore,
)

logger = logging.getLogger(__name__)


class PortfolioSnapshotProvider(Protocol):
    """
    Portfolio data source contract.
    
    Implementation must provide current portfolio state.
    """
    
    def get_snapshot(self) -> PortfolioSnapshot:
        """
        Get current portfolio snapshot.
        
        Returns:
            Immutable portfolio snapshot with positions and prices
        """
        ...


class GovernedOrderExecutor:
    """
    Portfolio-governed order executor wrapper.
    
    Adds pre-execution risk enforcement without modifying locked executor.
    
    Flow:
    1. Verify verdict is APPROVE
    2. Plan order (via locked planner)
    3. Get portfolio snapshot
    4. Evaluate governor
    5. Journal decision
    6. Enforce:
       - ALLOW / LOG_ONLY → execute
       - BLOCK → return error
       - MANUAL_REVIEW → return error
       - DOWNGRADE → execute dry_run
    """
    
    def __init__(
        self,
        planner: OrderPlanner,
        executor: OrderExecutor,
        governor: PositionExposureGovernor,
        snapshot_provider: PortfolioSnapshotProvider,
        journal: RiskGovernorJournal,
        window_store: WindowCounterStore,
        circuit_breaker: CircuitBreakerState,
        limits: RiskLimits,
    ):
        self.planner = planner
        self.executor = executor
        self.governor = governor
        self.snapshot_provider = snapshot_provider
        self.journal = journal
        self.window_store = window_store
        self.circuit_breaker = circuit_breaker
        self.limits = limits
    
    def execute_governed(
        self,
        verdict: CouncilVerdict,
        adapter,
        reference_price: float,
        adapter_name: str,
        equity: dict,
        now_ms: int,
    ) -> ExecutionResult:
        """
        Execute order with portfolio governance.
        
        Args:
            verdict: Council verdict (must be APPROVE)
            adapter: Exchange adapter
            reference_price: Market reference price
            adapter_name: Adapter identifier (for rate limits)
            equity: Portfolio equity info
            now_ms: Current timestamp (injected clock)
            
        Returns:
            ExecutionResult (may have error_code if blocked)
        """
        # ====================================================================
        # STEP 1: Verify verdict is APPROVE
        # ====================================================================
        
        if verdict.decision != "APPROVE":
            logger.info(
                f"⛔ Non-APPROVE verdict {verdict.id[:8]}: {verdict.decision}"
            )
            return ExecutionResult(
                plan_id="N/A",
                verdict_id=verdict.id,
                executed=False,
                exchange_order_id=None,
                filled_qty=0,
                avg_price=None,
                error_code="VERDICT_NOT_APPROVE",
                error_detail=f"Verdict decision: {verdict.decision}",
            )
        
        # ====================================================================
        # STEP 2: Plan order (via locked planner)
        # ====================================================================
        
        plan: OrderPlan = self.planner.plan(
            verdict=verdict,
            equity_snapshot=equity,
            reference_price=reference_price,
        )
        
        # Handle planner returning None (safety gates)
        if plan is None:
            logger.warning(
                f" Planner returned None (safety gate triggered) "
                f"[verdict={verdict.id[:8]}]"
            )
            return ExecutionResult(
                plan_id="N/A",
                verdict_id=verdict.id,
                executed=False,
                exchange_order_id=None,
                filled_qty=0,
                avg_price=None,
                error_code="PLANNER_REJECTED",
                error_detail="Planner safety gates triggered",
            )
        
        logger.info(
            f"📋 Order plan created: {plan.symbol} {plan.side} {plan.quantity:.6f} "
            f"(plan={plan.id[:8]}, verdict={verdict.id[:8]})"
        )
        
        # ====================================================================
        # STEP 3: Get portfolio snapshot
        # ====================================================================
        
        try:
            snapshot = self.snapshot_provider.get_snapshot()
        except Exception as e:
            logger.error(f"Failed to get portfolio snapshot: {e}", exc_info=True)
            snapshot = None
        
        # ====================================================================
        # STEP 4: Evaluate governor
        # ====================================================================
        
        governor_decision = self.governor.evaluate(
            verdict=verdict,
            plan=plan,
            snapshot=snapshot,
            adapter_name=adapter_name,
            now_ms=now_ms,
            limits=self.limits,
        )
        
        logger.info(
            f"🛡️ Governor decision: {governor_decision.decision} "
            f"({len(governor_decision.reason_codes)} reasons) "
            f"[plan={plan.id[:8]}]"
        )
        
        # ====================================================================
        # STEP 5: Journal decision
        # ====================================================================
        
        event = RiskGovernorEvent(
            verdict_id=verdict.id,
            plan_id=plan.id,
            symbol=plan.symbol,
            side=plan.side,
            decision=governor_decision.decision,
            reason_codes=governor_decision.reason_codes,
            reasoning=governor_decision.reasoning,
            computed_metrics=governor_decision.audit,
            limits_snapshot=governor_decision.limits_snapshot,
            correlation_cluster_id=governor_decision.correlation_cluster_id,
            window_count=governor_decision.window_count_orders_hour,
            consecutive_blocks=governor_decision.consecutive_blocks,
            halt_recommended=governor_decision.halt_recommended,
        )
        
        self.journal.record(event)
        
        # ====================================================================
        # STEP 6: Enforce decision
        # ====================================================================
        
        if governor_decision.decision == Decision.BLOCK:
            # BLOCKED: Return error result
            logger.warning(
                f"⛔ BLOCKED by governor: {governor_decision.reasoning} "
                f"[plan={plan.id[:8]}]"
            )
            
            if governor_decision.halt_recommended:
                logger.critical(
                    f"🚨 CIRCUIT BREAKER: {governor_decision.consecutive_blocks} "
                    f"consecutive blocks on {adapter_name}:{plan.symbol} — HALT RECOMMENDED"
                )
            
            return ExecutionResult(
                plan_id=plan.id,
                verdict_id=verdict.id,
                executed=False,
                exchange_order_id=None,
                filled_qty=0,
                avg_price=None,
                error_code="GOVERNOR_BLOCK",
                error_detail=governor_decision.reasoning,
            )
        
        elif governor_decision.decision == Decision.REQUIRES_MANUAL_REVIEW:
            # MANUAL REVIEW: Return error result
            logger.warning(
                f"⚠️ MANUAL REVIEW required: {governor_decision.reasoning} "
                f"[plan={plan.id[:8]}]"
            )
            
            return ExecutionResult(
                plan_id=plan.id,
                verdict_id=verdict.id,
                executed=False,
                exchange_order_id=None,
                filled_qty=0,
                avg_price=None,
                error_code="MANUAL_REVIEW_REQUIRED",
                error_detail=governor_decision.reasoning,
            )
        
        elif governor_decision.decision == Decision.DOWNGRADE_TO_DRY_RUN:
            # DOWNGRADE: Execute as dry run
            logger.warning(
                f"⬇️ DOWNGRADED to dry run: {governor_decision.reasoning} "
                f"[plan={plan.id[:8]}]"
            )
            
            return self.executor.execute(
                plan=plan,
                adapter=adapter,
                reference_price=reference_price,
                dry_run=True,  # DOWNGRADED
            )
        
        elif governor_decision.decision == Decision.LOG_ONLY:
            # SHADOW MODE: Allow but log
            logger.info(
                f"👁️ SHADOW MODE: Allowing + journaling [plan={plan.id[:8]}]"
            )
            
            return self.executor.execute(
                plan=plan,
                adapter=adapter,
                reference_price=reference_price,
                dry_run=False,
            )
        
        else:  # Decision.ALLOW
            # ALLOWED: Execute normally
            logger.info(
                f"✅ ALLOWED by governor [plan={plan.id[:8]}]"
            )
            
            return self.executor.execute(
                plan=plan,
                adapter=adapter,
                reference_price=reference_price,
                dry_run=False,
            )
