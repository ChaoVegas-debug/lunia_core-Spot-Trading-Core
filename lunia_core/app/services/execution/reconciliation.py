"""
EPOCH C: Reconciliation Engine (Component 7)
Crash-safe recovery with backoff, hard vs soft failure classification
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from .audit import emit_execution_audit, sanitize_exchange_response
from .exceptions import HardError, SoftError
from .models import OrderExecution, OrderExecutionStatus

logger = logging.getLogger(__name__)


class ExecutionReconciler:
    """
    Execution Reconciler
    
    Reconciles OrderExecution records with exchange truth.
    
    Features:
    - Startup scan for stuck orders (SUBMITTING older than threshold)
    - Backoff schedule to avoid exchange spam
    - Hard vs soft failure classification
    - DRY vs REAL separation
    """
    
    # Configuration
    STUCK_THRESHOLD_SEC = 30  # Orders older than 30s are "stuck"
    RECONCILE_BACKOFF_SCHEDULE = [5, 15, 30, 60, 120]  # Seconds between retries
    MAX_RECONCILE_ATTEMPTS = 5
    
    def __init__(self, adapter: Optional[Any] = None):
        """
        Initialize reconciler
        
        Args:
            adapter: Exchange adapter (required for REAL mode)
        """
        self.adapter = adapter
        self._reconcile_attempts: Dict[str, int] = {}  # client_order_id -> attempt count
        self._last_reconcile: Dict[str, datetime] = {}  # client_order_id -> last attempt timestamp
    
    def scan_stuck_orders(self, session: Session):
        """
        Scan for stuck orders and reconcile them
        
        Find orders in SUBMITTING status older than threshold.
        Respects backoff to avoid spamming exchange.
        
        Args:
            session: SQLAlchemy session
        """
        threshold = datetime.now(timezone.utc) - timedelta(seconds=self.STUCK_THRESHOLD_SEC)
        
        stuck_orders = session.query(OrderExecution).filter(
            OrderExecution.status == OrderExecutionStatus.SUBMITTING,
            OrderExecution.created_at < threshold
        ).all()
        
        logger.info(f"Found {len(stuck_orders)} stuck orders")
        
        for order_exec in stuck_orders:
            # Check backoff
            if not self._should_reconcile(order_exec.client_order_id):
                logger.debug(f"Skipping {order_exec.client_order_id} (backoff)")
                continue
            
            # Determine run mode from execution snapshot or default to "real"
            run_mode = "real"  # Default (would extract from execution_snapshot in production)
            
            try:
                self.reconcile_one(session, order_exec.client_order_id, run_mode)
            except Exception as e:
                logger.error(f"Reconciliation failed for {order_exec.client_order_id}: {e}")
                # Continue to next order
    
    def _should_reconcile(self, client_order_id: str) -> bool:
        """
        Check if order should be reconciled now (backoff check)
        
        Args:
            client_order_id: Client order ID
        
        Returns:
            True if should reconcile now
        """
        attempts = self._reconcile_attempts.get(client_order_id, 0)
        
        if attempts >= self.MAX_RECONCILE_ATTEMPTS:
            # Max attempts reached
            return False
        
        last_attempt = self._last_reconcile.get(client_order_id)
        
        if not last_attempt:
            # First attempt
            return True
        
        # Calculate backoff delay
        backoff_sec = self.RECONCILE_BACKOFF_SCHEDULE[
            min(attempts, len(self.RECONCILE_BACKOFF_SCHEDULE) - 1)
        ]
        
        next_attempt_time = last_attempt + timedelta(seconds=backoff_sec)
        
        return datetime.now(timezone.utc) >= next_attempt_time
    
    def reconcile_one(
        self,
        session: Session,
        client_order_id: str,
        run_mode: str
    ):
        """
        Reconcile a single order with exchange truth
        
        Args:
            session: SQLAlchemy session
            client_order_id: Client order ID to reconcile
            run_mode: "dry" or "real"
        """
        order_exec = session.query(OrderExecution).filter_by(
            client_order_id=client_order_id
        ).with_for_update().first()
        
        if not order_exec:
            logger.warning(f"Order {client_order_id} not found for reconciliation")
            return
        
        # Update backoff tracking
        self._reconcile_attempts[client_order_id] = self._reconcile_attempts.get(client_order_id, 0) + 1
        self._last_reconcile[client_order_id] = datetime.now(timezone.utc)
        
        # DRY MODE: Simulation only
        if run_mode == "dry":
            logger.info(f"[DRY] Reconciliation simulation for {client_order_id}")
            
            emit_execution_audit(
                session=session,
                event_type="RECOVERY_RECONCILIATION_SIMULATION",
                intent_id=None,  # Would extract from order_exec.order_plan.execution_intent_id
                plan_id=order_exec.order_plan_id,
                order_execution_id=order_exec.id,
                reason_codes=["DRY_MODE_SIMULATION"],
                metadata={"client_order_id": client_order_id}
            )
            
            session.commit()
            return
        
        # REAL MODE: Query exchange
        if not self.adapter:
            raise ValueError("No adapter configured for REAL mode reconciliation")
        
        try:
            # Query exchange by client_order_id
            exchange_order = self.adapter.get_order(client_order_id=client_order_id)
            
            # FOUND: Sync status
            logger.info(f"Reconciled {client_order_id}: found on exchange, status={exchange_order.get('status')}")
            
            exchange_status = exchange_order.get("status", "").upper()
            
            # Map exchange status to our status
            status_map = {
                "NEW": OrderExecutionStatus.SUBMITTED,
                "SUBMITTED": OrderExecutionStatus.SUBMITTED,
                "PARTIALLY_FILLED": OrderExecutionStatus.PARTIALLY_FILLED,
                "FILLED": OrderExecutionStatus.FILLED,
                "CANCELLED": OrderExecutionStatus.CANCELLED,
                "CANCELED": OrderExecutionStatus.CANCELLED,
                "REJECTED": OrderExecutionStatus.FAILED,
                "EXPIRED": OrderExecutionStatus.EXPIRED
            }
            
            new_status = status_map.get(exchange_status, order_exec.status)
            
            if new_status != order_exec.status:
                order_exec.status = new_status
                
                # Update exchange order ID if present
                if "orderId" in exchange_order or "id" in exchange_order:
                    order_exec.exchange_order_id = exchange_order.get("orderId") or exchange_order.get("id")
                
                # Update filled quantity if applicable
                if new_status in [OrderExecutionStatus.PARTIALLY_FILLED, OrderExecutionStatus.FILLED]:
                    order_exec.filled_quantity = float(exchange_order.get("executedQty", 0) or exchange_order.get("filled", 0))
                    
                    if new_status == OrderExecutionStatus.FILLED and not order_exec.filled_at:
                        order_exec.filled_at = datetime.now(timezone.utc)
                
                # Emit reconciliation audit
                event_type = {
                    OrderExecutionStatus.SUBMITTED: "RECOVERY_RECONCILIATION",
                    OrderExecutionStatus.PARTIALLY_FILLED: "ORDER_PARTIALLY_FILLED_RECONCILED",
                    OrderExecutionStatus.FILLED: "ORDER_FILLED_RECONCILED",
                    OrderExecutionStatus.CANCELLED: "ORDER_CANCELLED_RECONCILED",
                    OrderExecutionStatus.FAILED: "RECOVERY_RECONCILIATION",
                    OrderExecutionStatus.EXPIRED: "RECOVERY_RECONCILIATION"
                }.get(new_status, "RECOVERY_RECONCILIATION")
                
                emit_execution_audit(
                    session=session,
                    event_type=event_type,
                    intent_id=None,
                    plan_id=order_exec.order_plan_id,
                    order_execution_id=order_exec.id,
                    exchange_response=sanitize_exchange_response(exchange_order),
                    reason_codes=["RECONCILED", f"STATUS_WAS_{order_exec.status.value}_NOW_{new_status.value}"],
                    metadata={
                        "client_order_id": client_order_id,
                        "exchange_status": exchange_status,
                        "filled_qty": order_exec.filled_quantity
                    }
                )
                
                session.commit()
            
        except Exception as e:
            error_str = str(e).lower()
            
            # Check if NOT FOUND (definitive)
            if "not found" in error_str or "404" in error_str or "unknown order" in error_str:
                # NOT FOUND: Safe to mark FAILED
                logger.warning(f"Order {client_order_id} not found on exchange, marking FAILED")
                
                order_exec.status = OrderExecutionStatus.FAILED
                order_exec.exchange_response = {
                    "error": "Order not found on exchange",
                    "reconciliation": "NOT_FOUND"
                }
                
                emit_execution_audit(
                    session=session,
                    event_type="RECONCILIATION_ORDER_NOT_FOUND",
                    intent_id=None,
                    plan_id=order_exec.order_plan_id,
                    order_execution_id=order_exec.id,
                    reason_codes=["ORDER_NOT_FOUND", "SAFE_TERMINAL_FAILURE"],
                    metadata={"client_order_id": client_order_id}
                )
                
                session.commit()
                
            elif "timeout" in error_str or "network" in error_str or "502" in error_str or "503" in error_str or "504" in error_str:
                # SOFT ERROR: Keep SUBMITTING, schedule next retry
                logger.warning(f"Reconciliation soft error for {client_order_id}: {e}")
                
                # Keep status SUBMITTING
                order_exec.exchange_response = {
                    "error": str(e),
                    "reconciliation": "AMBIGUOUS",
                    "attempts": self._reconcile_attempts.get(client_order_id, 0)
                }
                
                emit_execution_audit(
                    session=session,
                    event_type="RECOVERY_RECONCILIATION",
                    intent_id=None,
                    plan_id=order_exec.order_plan_id,
                    order_execution_id=order_exec.id,
                    reason_codes=["RECONCILE_AMBIGUOUS", "SOFT_ERROR"],
                    metadata={
                        "client_order_id": client_order_id,
                        "error": str(e),
                        "attempts": self._reconcile_attempts.get(client_order_id, 0)
                    }
                )
                
                session.commit()
                
            else:
                # Unknown error - treat as soft (fail-closed ambiguous)
                logger.error(f"Unknown reconciliation error for {client_order_id}: {e}")
                
                order_exec.exchange_response = {
                    "error": str(e),
                    "reconciliation": "ERROR",
                    "attempts": self._reconcile_attempts.get(client_order_id, 0)
                }
                
                emit_execution_audit(
                    session=session,
                    event_type="RECOVERY_RECONCILIATION",
                    intent_id=None,
                    plan_id=order_exec.order_plan_id,
                    order_execution_id=order_exec.id,
                    reason_codes=["RECONCILE_ERROR", "UNKNOWN_ERROR"],
                    metadata={
                        "client_order_id": client_order_id,
                        "error": str(e)
                    }
                )
                
                session.commit()
