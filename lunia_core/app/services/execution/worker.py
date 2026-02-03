"""
EPOCH C: Execution Worker (Component 5)
Lease-based worker with DRY vs REAL separation, ambiguous-state handling, idempotency
"""
from __future__ import annotations

import logging
import socket
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from .audit import emit_execution_audit, AuditEventType, sanitize_exchange_response
from .exceptions import HardError, SoftError
from .governance_gate import ExecutionGovernanceGate
from .models import OrderExecution, OrderExecutionStatus, OrderPlan, QueueStatus
from .orchestrator import Orchestrator
from .orphan_guard import OrphanPositionGuard
from .price_guard import PriceSanityGuard
from .snapshots import capture_execution_snapshot
from ..auth.database import get_session
from ..proposal.models import ExecutionIntent

logger = logging.getLogger(__name__)


class ExecutionWorker:
    """
    Execution Worker
    
    Lease-based worker that processes ExecutionQueue items.
    
    Features:
    - Startup recovery (reconciles stuck orders)
    - Last-gasp governance check before any external action
    - DRY vs REAL separation (DRY never calls adapter)
    - Ambiguous-state handling (soft errors keep SUBMITTING)
    - Mandatory orphan guard invocation
    - Strict idempotency (client_order_id UNIQUE)
    """
    
    # Worker configuration
    LOOP_SLEEP_SEC = 1.0
    LEASE_RENEWAL_INTERVAL = 30  # Renew lease every 30s
    
    def __init__(
        self,
        adapter: Optional[Any] = None,
        worker_id: Optional[str] = None,
        reconciler: Optional[Any] = None,
        snapshot_provider: Optional[Any] = None
    ):
        """
        Initialize worker
        
        Args:
            adapter: Exchange adapter (required for REAL mode)
            worker_id: Worker identifier (defaults to hostname-pid-uuid)
            reconciler: Reconciliation engine (injected dependency)
            snapshot_provider: ThreadSafeSnapshotCache instance (required for REAL mode)
        """
        self.adapter = adapter
        self.worker_id = worker_id or self._generate_worker_id()
        self.reconciler = reconciler
        self.snapshot_provider = snapshot_provider
        self.price_guard = PriceSanityGuard()  # Instantiate guard
        self.running = False
        
        logger.info(f"ExecutionWorker initialized: {self.worker_id}")
    
    def _generate_worker_id(self) -> str:
        """Generate stable worker ID"""
        hostname = socket.gethostname()
        pid = time.process_time()
        uid = uuid.uuid4().hex[:8]
        return f"{hostname}-{pid}-{uid}"
    
    def startup_recovery(self, session: Session):
        """
        Startup recovery: reconcile stuck orders from crashes/restarts
        
        Args:
            session: SQLAlchemy session
        """
        logger.info(f"[{self.worker_id}] Running startup recovery...")
        
        if self.reconciler:
            try:
                self.reconciler.scan_stuck_orders(session)
                logger.info(f"[{self.worker_id}] Startup recovery complete")
            except Exception as e:
                logger.error(f"[{self.worker_id}] Startup recovery failed: {e}")
                # Don't crash - continue running
        else:
            logger.warning(f"[{self.worker_id}] No reconciler configured, skipping startup recovery")
    
    def run(self, max_iterations: Optional[int] = None):
        """
        Main worker loop
        
        Args:
            max_iterations: Max iterations (None = infinite). For testing only.
        """
        self.running = True
        iterations = 0
        
        logger.info(f"[{self.worker_id}] Worker starting...")
        
        # Startup recovery
        with get_session() as session:
            self.startup_recovery(session)
        
        while self.running:
            if max_iterations and iterations >= max_iterations:
                logger.info(f"[{self.worker_id}] Max iterations reached, stopping")
                break
            
            try:
                self._process_iteration()
            except Exception as e:
                logger.error(f"[{self.worker_id}] Iteration error: {e}", exc_info=True)
                # Don't crash - continue
            
            iterations += 1
            time.sleep(self.LOOP_SLEEP_SEC)
        
        logger.info(f"[{self.worker_id}] Worker stopped after {iterations} iterations")
    
    def stop(self):
        """Stop worker loop"""
        self.running = False
    
    def _process_iteration(self):
        """Process one iteration: claim job, execute, complete/fail"""
        with get_session() as session:
            orchestrator = Orchestrator(session, worker_id=self.worker_id)
            
            # Claim next job
            job = orchestrator.claim_next()
            
            if not job:
                # No work available
                return
            
            logger.info(f"[{self.worker_id}] Claimed job {job.id} for intent {job.intent_id}")
            
            try:
                # Process job
                self._process_job(session, orchestrator, job)
                
                # Mark complete
                orchestrator.complete(job.id)
                logger.info(f"[{self.worker_id}] Job {job.id} completed")
                
            except Exception as e:
                logger.error(f"[{self.worker_id}] Job {job.id} failed: {e}", exc_info=True)
                
                # Mark failed
                error_code = type(e).__name__
                error_message = str(e)
                orchestrator.fail(
                    job.id,
                    error_code=error_code,
                    error_message=error_message,
                    retry=True  # Retry on transient errors
                )
    
    def _process_job(self, session: Session, orchestrator: Orchestrator, job: Any):
        """
        Process a single execution job
        
        Args:
            session: SQLAlchemy session
            orchestrator: Orchestrator instance
            job: ExecutionQueue item
        """
        # Load intent
        intent = session.query(ExecutionIntent).filter_by(id=job.intent_id).first()
        if not intent:
            raise ValueError(f"Intent {job.intent_id} not found")
        
        # Load plan
        plan = session.query(OrderPlan).filter_by(execution_intent_id=intent.id).first()
        if not plan:
            raise ValueError(f"No plan found for intent {intent.id}")
        
        # Extract run mode
        run_mode = intent.run_mode or "dry"
        
        # Last-gasp governance check (MANDATORY before any external action)
        gov_decision = self._governance_last_gasp(session, intent, plan, run_mode)
        
        if gov_decision.decision != "ALLOW":
            # Governance blocked - emit audit and fail job
            emit_execution_audit(
                session=session,
                event_type=AuditEventType.INTENT_BLOCKED.value,
                intent_id=intent.id,
                plan_id=plan.id,
                worker_id=self.worker_id,
                reason_codes=gov_decision.reason_codes,
                metadata={"governance_snapshot": gov_decision.governance_snapshot}
            )
            
            raise ValueError(f"Governance blocked: {gov_decision.reason_codes}")
        
        # Execute orders in deterministic order
        orders = sorted(plan.orders, key=lambda o: o.get("order_index", 0))
        
        for order in orders:
            try:
                self._execute_order(session, intent, plan, order, run_mode)
            finally:
                # MANDATORY: Call orphan guard after EVERY attempt (success/fail)
                self._invoke_orphan_guard(session, intent, plan, run_mode)
    
    def _governance_last_gasp(
        self,
        session: Session,
        intent: ExecutionIntent,
        plan: OrderPlan,
        run_mode: str
    ) -> Any:
        """
        Last-gasp governance check (authoritative)
        
        Called immediately before any external action.
        
        Args:
            session: SQLAlchemy session
            intent: ExecutionIntent
            plan: OrderPlan
            run_mode: "dry" or "real"
        
        Returns:
            GovernanceDecision
        """
        gate = ExecutionGovernanceGate()
        
        # Get current state (would come from runtime in production)
        # For now, simplified - assumes governance snapshot exists
        market_data = None
        portfolio = None
        exchange_health = None
        
        decision = gate.check(
            run_mode=run_mode,
            market_data=market_data,
            portfolio=portfolio,
            exchange_health=exchange_health
        )
        
        return decision
    
    def _execute_order(
        self,
        session: Session,
        intent: ExecutionIntent,
        plan: OrderPlan,
        order: Dict[str, Any],
        run_mode: str
    ):
        """
        Execute a single order (with idempotency and ambiguous-state handling)
        
        Args:
            session: SQLAlchemy session
            intent: ExecutionIntent
            plan: OrderPlan
            order: Order dict from plan
            run_mode: "dry" or "real"
        """
        client_order_id = order.get("client_order_id")
        
        if not client_order_id:
            raise ValueError(f"Order missing client_order_id: {order}")
        
        # STEP 1: Idempotency pre-check (CRITICAL)
        existing = session.query(OrderExecution).filter_by(
            client_order_id=client_order_id
        ).first()
        
        if existing:
            logger.info(f"[{self.worker_id}] Order {client_order_id} already exists, status={existing.status}")
            
            # If already in terminal state, skip
            if existing.status in [
                OrderExecutionStatus.FILLED,
                OrderExecutionStatus.CANCELLED,
                OrderExecutionStatus.FAILED
            ]:
                return
            
            # If SUBMITTING/SUBMITTED, trigger reconciliation
            if existing.status in [OrderExecutionStatus.SUBMITTING, OrderExecutionStatus.SUBMITTED]:
                if self.reconciler:
                    self.reconciler.reconcile_one(session, client_order_id, run_mode)
                return
        
        # STEP 2: Create OrderExecution (Point of No Return)
        order_exec = OrderExecution(
            id=str(uuid.uuid4()),
            order_plan_id=plan.id,
            order_index=order.get("order_index", 0),
            client_order_id=client_order_id,
            symbol=order.get("symbol"),
            side=order.get("side"),
            order_type=order.get("order_type", "UNKNOWN"),
            order_style=order.get("order_style", "MARKET"),
            quantity=order.get("quantity", 0),
            price=order.get("price"),
            status=OrderExecutionStatus.PENDING
        )
        
        session.add(order_exec)
        session.flush()  # Get ID
        
        # Emit attempt audit
        emit_execution_audit(
            session=session,
            event_type=AuditEventType.ORDER_SUBMIT_ATTEMPTED.value,
            intent_id=intent.id,
            plan_id=plan.id,
            order_execution_id=order_exec.id,
            worker_id=self.worker_id,
            metadata={"client_order_id": client_order_id}
        )
        
        # STEP 3: DRY vs REAL mode
        if run_mode == "dry":
            # DRY MODE: Never call adapter
            order_exec.status = OrderExecutionStatus.SUBMITTED  # Simulation only
            
            emit_execution_audit(
                session=session,
                event_type="ORDER_SUBMITTED_SIMULATION",
                intent_id=intent.id,
                plan_id=plan.id,
                order_execution_id=order_exec.id,
                worker_id=self.worker_id,
                metadata={"client_order_id": client_order_id, "simulation": True}
            )
            
            session.commit()
            return
        
        # REAL MODE: Market Data Gate + Price Guard + Adapter call
        
        # STEP 4: Market Data Gate (O(1) non-blocking snapshot read)
        snapshot = None
        if self.snapshot_provider:
            try:
                # Zero-wait O(1) read from thread-safe cache
                snapshot = self.snapshot_provider.get(order.get("symbol"))
            except Exception as e:
                logger.error(f"[{self.worker_id}] Market data snapshot fetch failed: {e}")
                # Fail-closed: treat as missing snapshot
                snapshot = None
        
        # Check if we have market data in REAL mode
        if not snapshot:
            # BLOCK: No market data available
            order_exec.status = OrderExecutionStatus.FAILED
            
            emit_execution_audit(
                session=session,
                event_type="EXECUTION_BLOCKED",
                intent_id=intent.id,
                plan_id=plan.id,
                order_execution_id=order_exec.id,
                worker_id=self.worker_id,
                reason_codes=["EXECUTION_BLOCKED_MD_NO_SNAPSHOT"],
                metadata={
                    "symbol": order.get("symbol"),
                    "reason": "Market data snapshot not available",
                    "has_provider": self.snapshot_provider is not None
                }
            )
            
            session.commit()
            logger.warning(f"[{self.worker_id}] BLOCKED: No market data for {order.get('symbol')}")
            return
        
        # STEP 5: Price Sanity Guard (with double staleness check)
        guard_result = self.price_guard.validate(order, snapshot)
        
        if not guard_result.passed:
            # BLOCK: Price guard failed
            order_exec.status = OrderExecutionStatus.FAILED
            
            emit_execution_audit(
                session=session,
                event_type="EXECUTION_BLOCKED",
                intent_id=intent.id,
                plan_id=plan.id,
                order_execution_id=order_exec.id,
                worker_id=self.worker_id,
                reason_codes=[guard_result.reason_code],
                metadata={
                    "symbol": order.get("symbol"),
                    "guard_details": guard_result.details,
                    "snapshot_state": snapshot.snapshot_state.value,
                    "snapshot_version": snapshot.version
                }
            )
            
            session.commit()
            logger.warning(
                f"[{self.worker_id}] BLOCKED by price guard: {guard_result.reason_code} - {guard_result.details}"
            )
            return
        
        # All gates passed - proceed with submission
        order_exec.status = OrderExecutionStatus.SUBMITTING
        session.commit()  # Atomic boundary
        
        try:
            # Call adapter
            if not self.adapter:
                raise ValueError("No adapter configured for REAL mode")
            
            response = self.adapter.submit_order(
                symbol=order.get("symbol"),
                side=order.get("side"),
                quantity=order.get("quantity"),
                order_type=order.get("order_style", "MARKET"),
                price=order.get("price"),
                reduce_only=order.get("reduce_only", False),
                client_order_id=client_order_id
            )
            
            # SUCCESS
            order_exec.status = OrderExecutionStatus.SUBMITTED
            order_exec.exchange_order_id = response.get("orderId") or response.get("id")
            order_exec.submitted_at = datetime.now(timezone.utc)
            order_exec.exchange_response = response
            
            emit_execution_audit(
                session=session,
                event_type=AuditEventType.ORDER_SUBMITTED.value,
                intent_id=intent.id,
                plan_id=plan.id,
                order_execution_id=order_exec.id,
                worker_id=self.worker_id,
                exchange_response=sanitize_exchange_response(response),
                metadata={
                    "client_order_id": client_order_id,
                    "exchange_order_id": order_exec.exchange_order_id
                }
            )
            
            session.commit()
            
        except HardError as e:
            # HARD FAILURE: Definitive rejection - safe to mark FAILED
            order_exec.status = OrderExecutionStatus.FAILED
            order_exec.exchange_response = {"error": str(e), "error_type": "HardError"}
            
            emit_execution_audit(
                session=session,
                event_type=AuditEventType.ORDER_REJECTED.value,
                intent_id=intent.id,
                plan_id=plan.id,
                order_execution_id=order_exec.id,
                worker_id=self.worker_id,
                reason_codes=["HARD_FAILURE", type(e).__name__],
                metadata={"error": str(e)}
            )
            
            session.commit()
            raise
            
        except SoftError as e:
            # SOFT FAILURE / AMBIGUOUS: MUST NOT mark FAILED
            # Keep SUBMITTING and trigger reconciliation
            logger.warning(f"[{self.worker_id}] Soft error for {client_order_id}: {e}")
            
            # Record error but keep SUBMITTING
            order_exec.exchange_response = {
                "error": str(e),
                "error_type": "SoftError",
                "ambiguous": True
            }
            
            reason_code = "AMBIGUOUS_SUBMIT"
            if "timeout" in str(e).lower():
                reason_code = "SUBMIT_TIMEOUT"
            elif "network" in str(e).lower():
                reason_code = "NETWORK_FAILURE"
            elif "502" in str(e) or "503" in str(e) or "504" in str(e):
                reason_code = f"UPSTREAM_{str(e)[:3]}"
            
            emit_execution_audit(
                session=session,
                event_type="ORDER_SUBMIT_AMBIGUOUS",
                intent_id=intent.id,
                plan_id=plan.id,
                order_execution_id=order_exec.id,
                worker_id=self.worker_id,
                reason_codes=[reason_code],
                metadata={"error": str(e), "status": "SUBMITTING"}
            )
            
            session.commit()
            
            # Trigger reconciliation ASAP
            if self.reconciler:
                self.reconciler.reconcile_one(session, client_order_id, run_mode)
            
        except Exception as e:
            # Unknown exception - treat as soft error (fail-closed ambiguous)
            logger.error(f"[{self.worker_id}] Unknown error for {client_order_id}: {e}", exc_info=True)
            
            order_exec.exchange_response = {
                "error": str(e),
                "error_type": "UnknownError",
                "ambiguous": True
            }
            
            emit_execution_audit(
                session=session,
                event_type="ORDER_SUBMIT_AMBIGUOUS",
                intent_id=intent.id,
                plan_id=plan.id,
                order_execution_id=order_exec.id,
                worker_id=self.worker_id,
                reason_codes=["UNKNOWN_ERROR", "AMBIGUOUS_SUBMIT"],
                metadata={"error": str(e)}
            )
            
            session.commit()
            raise
    
    def _invoke_orphan_guard(
        self,
        session: Session,
        intent: ExecutionIntent,
        plan: OrderPlan,
        run_mode: str
    ):
        """
        Invoke Orphan Position Guard (MANDATORY after every order attempt)
        
        Args:
            session: SQLAlchemy session
            intent: ExecutionIntent
            plan: OrderPlan
            run_mode: "dry" or "real"
        """
        guard = OrphanPositionGuard()
        
        # Get order executions for this plan
        executions = session.query(OrderExecution).filter_by(
            order_plan_id=plan.id
        ).all()
        
        execution_dicts = [
            {
                "client_order_id": e.client_order_id,
                "status": e.status.value if hasattr(e.status, "value") else str(e.status),
                "filled_at": e.filled_at,
                "filled_qty": e.filled_quantity
            }
            for e in executions
        ]
        
        # Position state (simplified - would come from portfolio service)
        position_state = {
            "position_qty": 0.1,  # Placeholder
            "entry_filled_qty": 0.1,  # Placeholder
            "symbol": plan.orders[0].get("symbol") if plan.orders else "UNKNOWN"
        }
        
        # Governance snapshot
        from ...core.state import get_state
        runtime_state = get_state()
        governance_snapshot = {
            "global_stop": runtime_state.get("global_stop", False),
            "system_mode": runtime_state.get("system_mode", "MANUAL"),
            "airlock_status": runtime_state.get("airlock_status", "NOT_READY")
        }
        
        # Audit emit wrapper
        def audit_emit(**kwargs):
            emit_execution_audit(session=session, **kwargs)
        
        # Evaluate and act
        result = guard.evaluate_and_act(
            intent_id=intent.id,
            plan={"id": plan.id, "orders": plan.orders, "plan_version": plan.plan_version, "asset": plan.orders[0].get("symbol") if plan.orders else "UNKNOWN"},
            order_executions=execution_dicts,
            run_mode=run_mode,
            governance_snapshot=governance_snapshot,
            position_state=position_state,
            now_utc=datetime.now(timezone.utc),
            adapter=self.adapter if run_mode == "real" else None,
            audit_emit=audit_emit,
            sanitize_exchange_response=sanitize_exchange_response
        )
        
        logger.info(f"[{self.worker_id}] Orphan guard result: {result['decision']}")
