"""
PHASE 14D — EXECUTION MONITORING: Monitor (Post-Trade Observer)

Reconciles execution ambiguity and tracks order lifecycle.

CRITICAL GOVERNANCE:
- Read-only observer (only calls get_order_status)
- Hands not brain (no trading decisions)
- Fail-closed (exceptions → UNRESOLVED)
- Deterministic (no wall-clock)
- Audit binding (M1 → M2 → M3)

DANGER: Do NOT use this to decide trades.
This is for post-trade truth verification only.
"""

from typing import Dict, Any, Optional

from .models import (
    ReconciliationResult,
    ReconciliationStatus,
    MonitorStatus,
    stable_json,
    canonical_ts,
)

# Import execution client (read-only usage)
from extensions.exchange_connectivity.execution_client import BinanceExecutionClient
from extensions.exchange_connectivity.trade_models import OrderResult

# Import audit store
from extensions.genome_dsl.audit_store import AuditStore


# ────────────────────────────────────────────────────────────────────────────────
# EXECUTION MONITOR (POST-TRADE OBSERVER)
# ────────────────────────────────────────────────────────────────────────────────

class ExecutionMonitor:
    """
    Post-trade execution monitoring and reconciliation.
    
    Responsibilities:
    - Resolve UNKNOWN order statuses via get_order_status
    - Classify terminal vs active orders
    - Emit deterministic audit trail (M1 → M2 → M3)
    
    Rules:
    - READ ONLY (never calls create_order/cancel_order)
    - Fail-closed (exceptions → UNRESOLVED)
    - No retries (single query attempt)
    - Stateless (no memory between calls)
    """
    
    def __init__(
        self,
        client: BinanceExecutionClient,
        audit_store: AuditStore,
        *,
        max_audits: int = 10,
    ):
        """
        Initialize execution monitor.
        
        Args:
            client: BinanceExecutionClient (for get_order_status)
            audit_store: AuditStore (audit persistence)
            max_audits: Max audits to include in result (bounded)
        """
        self._client = client
        self._audit_store = audit_store
        self._max_audits = max_audits
    
    def reconcile(self, routing_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reconcile execution result (POST-TRADE OBSERVER).
        
        Args:
            routing_result: RoutingResult dict from router (Phase 14C)
        
        Returns:
            ReconciliationResult as dict (never throws)
        
        Algorithm (STRICT ORDER, FAIL-CLOSED):
        1. Extract routing_result components
        2. Append MONITOR_INPUT audit (M1)
        3. If BLOCKED → FINAL (no reconciliation)
        4. If definitive status → FINAL (no reconciliation)
        5. If UNKNOWN/PARTIAL_FAILURE → reconcile via get_order_status
        6. If NEW/PARTIALLY_FILLED → PENDING (active)
        7. Append MONITOR_SUMMARY audit (M3)
        8. Return ReconciliationResult
        """
        audits_collected = []
        
        try:
            return self._reconcile_internal(routing_result, audits_collected)
        except Exception as e:
            # Unexpected exception → fail-closed UNRESOLVED
            error = {
                "code": "MONITOR_000",
                "message": f"Unexpected monitor error: {str(e)}",
                "type": type(e).__name__,
            }
            
            # Create minimal safe result
            result = ReconciliationResult(
                status="UNRESOLVED",
                ts_ms=routing_result.get("ts_ms"),
                decision_id=routing_result.get("decision_id", "unknown"),
                client_order_id=routing_result.get("client_order_id"),
                order_id=None,
                initial=routing_result,
                reconciled=None,
                monitor_status="ERROR",
                error=error,
                audits=audits_collected[:self._max_audits],
            )
            
            return result.to_dict()
    
    def _reconcile_internal(
        self,
        routing_result: Dict[str, Any],
        audits_collected: list,
    ) -> Dict[str, Any]:
        """
        Internal reconciliation logic (fail-fast).
        
        This method assumes caller catches exceptions.
        """
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 1: Extract components
        # ─────────────────────────────────────────────────────────────────────────
        
        routing_status = routing_result.get("status")
        decision_id = routing_result.get("decision_id", "unknown")
        client_order_id = routing_result.get("client_order_id")
        order_result = routing_result.get("order_result", {})
        
        # Extract order_id and initial status
        order_id = order_result.get("order_id") if order_result else None
        initial_status = order_result.get("status") if order_result else None
        symbol = order_result.get("symbol") if order_result else None
        
        # Canonical timestamp
        ts_ms = canonical_ts(
            routing_result.get("ts_ms"),
            order_result.get("ts_ms") if isinstance(order_result, dict) else None,
        )
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 2: Append MONITOR_INPUT audit (M1) - ALWAYS
        # ─────────────────────────────────────────────────────────────────────────
        
        monitor_input_audit = {
            "schema_version": "1.0.0",
            "phase": "14D",
            "event": "MONITOR_INPUT",
            "timestamp_ms": ts_ms,
            "symbol": symbol,
            "data": {
                "decision_id": decision_id,
                "client_order_id": client_order_id,
                "order_id": order_id,
                "routing_status": routing_status,
                "initial_status": initial_status,
            },
        }
        
        self._audit_store.append(monitor_input_audit)
        audits_collected.append(monitor_input_audit)
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 3: If BLOCKED → FINAL (no execution, no reconciliation needed)
        # ─────────────────────────────────────────────────────────────────────────
        
        if routing_status == "BLOCKED":
            # No order submitted → FINAL
            summary_audit = {
                "schema_version": "1.0.0",
                "phase": "14D",
                "event": "MONITOR_SUMMARY",
                "timestamp_ms": ts_ms,
                "symbol": symbol,
                "data": {
                    "reconciliation_status": "FINAL",
                    "monitor_status": "OK",
                    "reason": "Blocked by gateway, no execution",
                    "decision_id": decision_id,
                },
            }
            
            self._audit_store.append(summary_audit)
            audits_collected.append(summary_audit)
            
            result = ReconciliationResult(
                status="FINAL",
                ts_ms=ts_ms,
                decision_id=decision_id,
                client_order_id=client_order_id,
                order_id=order_id,
                initial=routing_result,
                reconciled=None,
                monitor_status="OK",
                audits=audits_collected[:self._max_audits],
            )
            
            return result.to_dict()
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 4: Classify initial status
        # ─────────────────────────────────────────────────────────────────────────
        
        # Definitive terminal states (no reconciliation needed)
        if initial_status in ["FILLED", "REJECTED", "CANCELED"]:
            summary_audit = {
                "schema_version": "1.0.0",
                "phase": "14D",
                "event": "MONITOR_SUMMARY",
                "timestamp_ms": ts_ms,
                "symbol": symbol,
                "data": {
                    "reconciliation_status": "FINAL",
                    "monitor_status": "OK",
                    "reason": f"Terminal status: {initial_status}",
                    "decision_id": decision_id,
                    "initial_status": initial_status,
                },
            }
            
            self._audit_store.append(summary_audit)
            audits_collected.append(summary_audit)
            
            result = ReconciliationResult(
                status="FINAL",
                ts_ms=ts_ms,
                decision_id=decision_id,
                client_order_id=client_order_id,
                order_id=order_id,
                initial=routing_result,
                reconciled=None,
                monitor_status="OK",
                audits=audits_collected[:self._max_audits],
            )
            
            return result.to_dict()
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 5: UNKNOWN or PARTIAL_FAILURE → Reconcile via get_order_status
        # ─────────────────────────────────────────────────────────────────────────
        
        if initial_status == "UNKNOWN" or routing_status == "PARTIAL_FAILURE":
            # Need reconciliation
            if not symbol:
                # Cannot reconcile without symbol
                error = {
                    "code": "MONITOR_001_MISSING_SYMBOL",
                    "message": "Cannot reconcile: symbol missing",
                }
                
                summary_audit = {
                    "schema_version": "1.0.0",
                    "phase": "14D",
                    "event": "MONITOR_SUMMARY",
                    "timestamp_ms": ts_ms,
                    "symbol": symbol,
                    "data": {
                        "reconciliation_status": "UNRESOLVED",
                        "monitor_status": "ERROR",
                        "error": error,
                        "decision_id": decision_id,
                    },
                }
                
                self._audit_store.append(summary_audit)
                audits_collected.append(summary_audit)
                
                result = ReconciliationResult(
                    status="UNRESOLVED",
                    ts_ms=ts_ms,
                    decision_id=decision_id,
                    client_order_id=client_order_id,
                    order_id=order_id,
                    initial=routing_result,
                    reconciled=None,
                    monitor_status="ERROR",
                    error=error,
                    audits=audits_collected[:self._max_audits],
                )
                
                return result.to_dict()
            
            if not order_id and not client_order_id:
                # Cannot query without identifier
                error = {
                    "code": "MONITOR_002_MISSING_IDENTIFIER",
                    "message": "Cannot reconcile: both order_id and client_order_id missing",
                }
                
                summary_audit = {
                    "schema_version": "1.0.0",
                    "phase": "14D",
                    "event": "MONITOR_SUMMARY",
                    "timestamp_ms": ts_ms,
                    "symbol": symbol,
                    "data": {
                        "reconciliation_status": "UNRESOLVED",
                        "monitor_status": "ERROR",
                        "error": error,
                        "decision_id": decision_id,
                    },
                }
                
                self._audit_store.append(summary_audit)
                audits_collected.append(summary_audit)
                
                result = ReconciliationResult(
                    status="UNRESOLVED",
                    ts_ms=ts_ms,
                    decision_id=decision_id,
                    client_order_id=client_order_id,
                    order_id=order_id,
                    initial=routing_result,
                    reconciled=None,
                    monitor_status="ERROR",
                    error=error,
                    audits=audits_collected[:self._max_audits],
                )
                
                return result.to_dict()
            
            # Call get_order_status (single attempt, no retries)
            try:
                reconciled_order = self._client.get_order_status(
                    symbol=symbol,
                    order_id=order_id,
                    client_order_id=client_order_id,
                )
                
                reconciled_dict = reconciled_order.to_dict()
                reconciled_status = reconciled_order.status
                
                # Append reconcile audit (M2)
                reconcile_audit = {
                    "schema_version": "1.0.0",
                    "phase": "14D",
                    "event": "MONITOR_RECONCILE_RESULT",
                    "timestamp_ms": ts_ms,
                    "symbol": symbol,
                    "data": {
                        "decision_id": decision_id,
                        "client_order_id": reconciled_order.client_order_id,
                        "order_id": reconciled_order.order_id,
                        "reconciled_status": reconciled_status,
                        "initial_status": initial_status,
                    },
                }
                
                self._audit_store.append(reconcile_audit)
                audits_collected.append(reconcile_audit)
                
                # Classify reconciled status
                if reconciled_status in ["FILLED", "REJECTED", "CANCELED"]:
                    recon_status = "FINAL"
                elif reconciled_status in ["NEW", "PARTIALLY_FILLED"]:
                    recon_status = "PENDING"
                elif reconciled_status == "UNKNOWN":
                    recon_status = "UNRESOLVED"
                else:
                    recon_status = "UNRESOLVED"
                
                # Append summary audit (M3)
                summary_audit = {
                    "schema_version": "1.0.0",
                    "phase": "14D",
                    "event": "MONITOR_SUMMARY",
                    "timestamp_ms": ts_ms,
                    "symbol": symbol,
                    "data": {
                        "reconciliation_status": recon_status,
                        "monitor_status": "OK",
                        "reconciled_status": reconciled_status,
                        "decision_id": decision_id,
                    },
                }
                
                self._audit_store.append(summary_audit)
                audits_collected.append(summary_audit)
                
                result = ReconciliationResult(
                    status=recon_status,
                    ts_ms=ts_ms,
                    decision_id=decision_id,
                    client_order_id=reconciled_order.client_order_id,
                    order_id=reconciled_order.order_id,
                    initial=routing_result,
                    reconciled=reconciled_dict,
                    monitor_status="OK",
                    audits=audits_collected[:self._max_audits],
                )
                
                return result.to_dict()
            
            except Exception as e:
                # Reconciliation failed → UNRESOLVED
                error = {
                    "code": "MONITOR_003_RECONCILE_FAILED",
                    "message": f"get_order_status failed: {str(e)}",
                    "type": type(e).__name__,
                }
                
                # Append reconcile error audit (M2)
                reconcile_audit = {
                    "schema_version": "1.0.0",
                    "phase": "14D",
                    "event": "MONITOR_RECONCILE_RESULT",
                    "timestamp_ms": ts_ms,
                    "symbol": symbol,
                    "data": {
                        "decision_id": decision_id,
                        "client_order_id": client_order_id,
                        "order_id": order_id,
                        "error": error,
                    },
                }
                
                self._audit_store.append(reconcile_audit)
                audits_collected.append(reconcile_audit)
                
                # Append summary audit (M3)
                summary_audit = {
                    "schema_version": "1.0.0",
                    "phase": "14D",
                    "event": "MONITOR_SUMMARY",
                    "timestamp_ms": ts_ms,
                    "symbol": symbol,
                    "data": {
                        "reconciliation_status": "UNRESOLVED",
                        "monitor_status": "ERROR",
                        "error": error,
                        "decision_id": decision_id,
                    },
                }
                
                self._audit_store.append(summary_audit)
                audits_collected.append(summary_audit)
                
                result = ReconciliationResult(
                    status="UNRESOLVED",
                    ts_ms=ts_ms,
                    decision_id=decision_id,
                    client_order_id=client_order_id,
                    order_id=order_id,
                    initial=routing_result,
                    reconciled=None,
                    monitor_status="ERROR",
                    error=error,
                    audits=audits_collected[:self._max_audits],
                )
                
                return result.to_dict()
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 6: NEW or PARTIALLY_FILLED → PENDING (active order)
        # ─────────────────────────────────────────────────────────────────────────
        
        if initial_status in ["NEW", "PARTIALLY_FILLED"]:
            summary_audit = {
                "schema_version": "1.0.0",
                "phase": "14D",
                "event": "MONITOR_SUMMARY",
                "timestamp_ms": ts_ms,
                "symbol": symbol,
                "data": {
                    "reconciliation_status": "PENDING",
                    "monitor_status": "OK",
                    "reason": f"Active order: {initial_status}",
                    "decision_id": decision_id,
                    "initial_status": initial_status,
                },
            }
            
            self._audit_store.append(summary_audit)
            audits_collected.append(summary_audit)
            
            result = ReconciliationResult(
                status="PENDING",
                ts_ms=ts_ms,
                decision_id=decision_id,
                client_order_id=client_order_id,
                order_id=order_id,
                initial=routing_result,
                reconciled=None,
                monitor_status="OK",
                audits=audits_collected[:self._max_audits],
            )
            
            return result.to_dict()
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 7: Unknown initial status → UNRESOLVED
        # ─────────────────────────────────────────────────────────────────────────
        
        error = {
            "code": "MONITOR_004_UNKNOWN_STATUS",
            "message": f"Unknown initial status: {initial_status}",
        }
        
        summary_audit = {
            "schema_version": "1.0.0",
            "phase": "14D",
            "event": "MONITOR_SUMMARY",
            "timestamp_ms": ts_ms,
            "symbol": symbol,
            "data": {
                "reconciliation_status": "UNRESOLVED",
                "monitor_status": "DEGRADED",
                "error": error,
                "decision_id": decision_id,
            },
        }
        
        self._audit_store.append(summary_audit)
        audits_collected.append(summary_audit)
        
        result = ReconciliationResult(
            status="UNRESOLVED",
            ts_ms=ts_ms,
            decision_id=decision_id,
            client_order_id=client_order_id,
            order_id=order_id,
            initial=routing_result,
            reconciled=None,
            monitor_status="DEGRADED",
            error=error,
            audits=audits_collected[:self._max_audits],
        )
        
        return result.to_dict()
