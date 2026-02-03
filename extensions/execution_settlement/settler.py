"""
PHASE 14E — EXECUTION SETTLEMENT: Settler (Settlement Orchestrator)

Post-trade settlement orchestrator with strict fail-closed semantics.

CRITICAL GOVERNANCE:
- Zero double counting (idempotency)
- Truth priority (reconciliation > routing)
- Ledger-first (portfolio failure doesn't revert)
- Final-state only (FILLED/REJECTED/CANCELED)
- No trading (read-only relative to exchange)
- Deterministic (no wall-clock)
"""

from typing import Dict, Any, Optional

from .models import (
    SettlementResult,
    SettlementStatus,
    SkipReason,
    SettlementError,
    PortfolioApplyResult,
    PortfolioSink,
    stable_json,
    canonical_ts,
    is_terminal_status,
    derive_idempotency_key,
    extract_truth,
)
from .ledger import ExecutionLedger
from extensions.genome_dsl.audit_store import AuditStore


# ────────────────────────────────────────────────────────────────────────────────
# EXECUTION SETTLER (SETTLEMENT ORCHESTRATOR)
# ────────────────────────────────────────────────────────────────────────────────

class ExecutionSettler:
    """
    Post-trade settlement orchestrator (fail-fast, fail-closed).
    
    Responsibilities:
    - Extract truth from routing/reconciliation
    - Filter final states (MVP: FILLED/REJECTED/CANCELED)
    - Ensure idempotency (no double counting)
    - Ledger-first persistence
    - Portfolio apply (if applicable)
    - Emit complete audit trail
    
    Rules:
    - No trading capability
    - No retries (single attempt)
    - Deterministic outputs
    - Bounded audits
    """
    
    def __init__(
        self,
        ledger: ExecutionLedger,
        audit_store: AuditStore,
        portfolio_sink: Optional[PortfolioSink] = None,
        *,
        max_audits: int = 10,
    ):
        """
        Initialize execution settler.
        
        Args:
            ledger: ExecutionLedger (append-only)
            audit_store: AuditStore (audit persistence)
            portfolio_sink: PortfolioSink (optional, for apply_fill)
            max_audits: Max audits to include in result (bounded)
        """
        self._ledger = ledger
        self._audit_store = audit_store
        self._portfolio_sink = portfolio_sink
        self._max_audits = max_audits
    
    def settle(
        self,
        routing_result: Dict[str, Any],
        reconciliation_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Settle execution result (POST-TRADE SETTLEMENT).
        
        Args:
            routing_result: RoutingResult dict from Phase 14C
            reconciliation_result: ReconciliationResult dict from Phase 14D (optional)
        
        Returns:
            SettlementResult as dict (never throws)
        
        Algorithm (STRICT ORDER, FAIL-CLOSED):
        1. Validate routing_result shape
        2. Append E1 SETTLEMENT_INPUT (always)
        3. Extract truth (reconciliation > routing)
        4. Filter final-state (FILLED/REJECTED/CANCELED only)
        5. Check idempotency (already_applied?)
        6. LEDGER-FIRST: Append to ledger
        7. PORTFOLIO APPLY: If FILLED + portfolio_sink
        8. Append E4 SETTLEMENT_SUMMARY (always)
        9. Return SettlementResult
        """
        audits_collected = []
        
        try:
            return self._settle_internal(routing_result, reconciliation_result, audits_collected)
        except Exception as e:
            # Unexpected exception → fail-closed ERROR
            error = {
                "code": "SETTLEMENT_000_UNEXPECTED",
                "message": f"Unexpected settlement error: {str(e)}",
                "type": type(e).__name__,
            }
            
            # Create minimal safe result
            result = SettlementResult(
                status="ERROR",
                ts_ms=routing_result.get("ts_ms"),
                decision_id=routing_result.get("decision_id", "unknown"),
                client_order_id=routing_result.get("client_order_id"),
                order_id=None,
                symbol=None,
                truth_source="NONE",
                terminal_status="NONE",
                idempotency_key="",
                already_applied=False,
                audits=audits_collected[:self._max_audits],
                error=error,
            )
            
            return result.to_dict()
    
    def _settle_internal(
        self,
        routing_result: Dict[str, Any],
        reconciliation_result: Optional[Dict[str, Any]],
        audits_collected: list,
    ) -> Dict[str, Any]:
        """
        Internal settlement logic (fail-fast).
        
        This method assumes caller catches exceptions.
        """
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 1: Validate routing_result shape
        # ─────────────────────────────────────────────────────────────────────────
        
        decision_id = routing_result.get("decision_id")
        if not decision_id:
            # Try decision dict
            decision = routing_result.get("decision", {})
            decision_id = decision.get("id") if isinstance(decision, dict) else None
        
        if not decision_id:
            # Missing decision_id → ERROR
            error = SettlementError(
                code="SETTLEMENT_001_MISSING_DECISION_ID",
                message="Cannot settle: decision_id missing",
            )
            
            result = SettlementResult(
                status="ERROR",
                ts_ms=routing_result.get("ts_ms"),
                decision_id="unknown",
                client_order_id=routing_result.get("client_order_id"),
                order_id=None,
                symbol=None,
                truth_source="NONE",
                terminal_status="NONE",
                idempotency_key="",
                already_applied=False,
                skip_reason="MISSING_DATA",
                error=error.to_dict(),
            )
            
            return result.to_dict()
        
        routing_status = routing_result.get("status")
        ts_ms = canonical_ts(
            routing_result.get("ts_ms"),
            reconciliation_result.get("ts_ms") if reconciliation_result else None,
        )
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 2: Append E1 SETTLEMENT_INPUT (always)
        # ─────────────────────────────────────────────────────────────────────────
        
        input_audit = {
            "schema_version": "1.0.0",
            "phase": "14E",
            "event": "SETTLEMENT_INPUT",
            "timestamp_ms": ts_ms,
            "symbol": None,  # Will be set after truth extraction
            "data": {
                "decision_id": decision_id,
                "routing_status": routing_status,
                "has_reconciliation": reconciliation_result is not None,
            },
        }
        
        self._audit_store.append(input_audit)
        audits_collected.append(input_audit)
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 3: If BLOCKED → SKIPPED (no execution, no settlement)
        # ─────────────────────────────────────────────────────────────────────────
        
        if routing_status == "BLOCKED":
            summary_audit = {
                "schema_version": "1.0.0",
                "phase": "14E",
                "event": "SETTLEMENT_SUMMARY",
                "timestamp_ms": ts_ms,
                "symbol": None,
                "data": {
                    "settlement_status": "SKIPPED",
                    "skip_reason": "BLOCKED",
                    "decision_id": decision_id,
                },
            }
            
            self._audit_store.append(summary_audit)
            audits_collected.append(summary_audit)
            
            result = SettlementResult(
                status="SKIPPED",
                ts_ms=ts_ms,
                decision_id=decision_id,
                client_order_id=routing_result.get("client_order_id"),
                order_id=None,
                symbol=None,
                truth_source="NONE",
                terminal_status="NONE",
                idempotency_key="",
                already_applied=False,
                skip_reason="BLOCKED",
                audits=audits_collected[:self._max_audits],
            )
            
            return result.to_dict()
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 4: Extract truth (reconciliation > routing)
        # ─────────────────────────────────────────────────────────────────────────
        
        truth_order, truth_source, terminal_status = extract_truth(routing_result, reconciliation_result)
        
        if truth_order is None or truth_source == "NONE":
            # NO_TRUTH → ERROR
            error = SettlementError(
                code="SETTLEMENT_002_NO_TRUTH",
                message="Cannot extract truth OrderResult from routing/reconciliation",
            )
            
            summary_audit = {
                "schema_version": "1.0.0",
                "phase": "14E",
                "event": "SETTLEMENT_SUMMARY",
                "timestamp_ms": ts_ms,
                "symbol": None,
                "data": {
                    "settlement_status": "ERROR",
                    "error": error.to_dict(),
                    "decision_id": decision_id,
                },
            }
            
            self._audit_store.append(summary_audit)
            audits_collected.append(summary_audit)
            
            result = SettlementResult(
                status="ERROR",
                ts_ms=ts_ms,
                decision_id=decision_id,
                client_order_id=routing_result.get("client_order_id"),
                order_id=None,
                symbol=None,
                truth_source="NONE",
                terminal_status="NONE",
                idempotency_key="",
                already_applied=False,
                skip_reason="NO_TRUTH",
                error=error.to_dict(),
                audits=audits_collected[:self._max_audits],
            )
            
            return result.to_dict()
        
        # Extract order details
        symbol = truth_order.get("symbol")
        client_order_id = truth_order.get("client_order_id")
        order_id = truth_order.get("order_id")
        filled_qty_str = truth_order.get("filled_qty", "0")
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 5: FINAL-STATE FILTER (MVP: FILLED/REJECTED/CANCELED only)
        # ─────────────────────────────────────────────────────────────────────────
        
        if not is_terminal_status(terminal_status):
            # Non-terminal → SKIPPED NOT_FINAL
            summary_audit = {
                "schema_version": "1.0.0",
                "phase": "14E",
                "event": "SETTLEMENT_SUMMARY",
                "timestamp_ms": ts_ms,
                "symbol": symbol,
                "data": {
                    "settlement_status": "SKIPPED",
                    "skip_reason": "NOT_FINAL",
                    "terminal_status": terminal_status,
                    "decision_id": decision_id,
                },
            }
            
            self._audit_store.append(summary_audit)
            audits_collected.append(summary_audit)
            
            result = SettlementResult(
                status="SKIPPED",
                ts_ms=ts_ms,
                decision_id=decision_id,
                client_order_id=client_order_id,
                order_id=order_id,
                symbol=symbol,
                truth_source=truth_source,
                terminal_status=terminal_status,
                idempotency_key="",
                already_applied=False,
                skip_reason="NOT_FINAL",
                audits=audits_collected[:self._max_audits],
            )
            
            return result.to_dict()
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 6: Compute idempotency key
        # ─────────────────────────────────────────────────────────────────────────
        
        idempotency_key = derive_idempotency_key(
            decision_id=decision_id,
            client_order_id=client_order_id,
            order_id=order_id,
            terminal_status=terminal_status,
            filled_qty_str=filled_qty_str,
        )
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 7: Check idempotency (DOUBLE COUNTING IMMUNITY)
        # ─────────────────────────────────────────────────────────────────────────
        
        if self._ledger.has_processed(idempotency_key):
            # Already applied → SKIPPED ALREADY_APPLIED
            summary_audit = {
                "schema_version": "1.0.0",
                "phase": "14E",
                "event": "SETTLEMENT_SUMMARY",
                "timestamp_ms": ts_ms,
                "symbol": symbol,
                "data": {
                    "settlement_status": "SKIPPED",
                    "skip_reason": "ALREADY_APPLIED",
                    "idempotency_key": idempotency_key,
                    "decision_id": decision_id,
                },
            }
            
            self._audit_store.append(summary_audit)
            audits_collected.append(summary_audit)
            
            result = SettlementResult(
                status="SKIPPED",
                ts_ms=ts_ms,
                decision_id=decision_id,
                client_order_id=client_order_id,
                order_id=order_id,
                symbol=symbol,
                truth_source=truth_source,
                terminal_status=terminal_status,
                idempotency_key=idempotency_key,
                already_applied=True,
                skip_reason="ALREADY_APPLIED",
                audits=audits_collected[:self._max_audits],
            )
            
            return result.to_dict()
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 8: LEDGER-FIRST (append to ledger)
        # ─────────────────────────────────────────────────────────────────────────
        
        ledger_entry = {
            "decision_id": decision_id,
            "client_order_id": client_order_id,
            "order_id": order_id,
            "symbol": symbol,
            "terminal_status": terminal_status,
            "filled_qty": filled_qty_str,
            "avg_price": truth_order.get("avg_price", "0"),
            "fees": truth_order.get("fees", "0"),
            "truth_source": truth_source,
            "ts_ms": ts_ms,
        }
        
        ledger_ref = self._ledger.record_trade(ledger_entry, idempotency_key=idempotency_key)
        
        # Append E2 LEDGER_APPEND
        ledger_audit = {
            "schema_version": "1.0.0",
            "phase": "14E",
            "event": "LEDGER_APPEND",
            "timestamp_ms": ts_ms,
            "symbol": symbol,
            "data": {
                "ledger_ref": ledger_ref,
                "idempotency_key": idempotency_key,
                "terminal_status": terminal_status,
                "decision_id": decision_id,
            },
        }
        
        self._audit_store.append(ledger_audit)
        audits_collected.append(ledger_audit)
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 9: PORTFOLIO APPLY (only if FILLED + portfolio_sink provided)
        # ─────────────────────────────────────────────────────────────────────────
        
        portfolio_updated = False
        portfolio_ref = None
        settlement_status: SettlementStatus = "APPLIED"
        error_dict = None
        
        if terminal_status == "FILLED" and self._portfolio_sink:
            # Attempt portfolio apply
            trade = {
                "symbol": symbol,
                "side": truth_order.get("side", "UNKNOWN"),
                "quantity": filled_qty_str,
                "price": truth_order.get("avg_price", "0"),
                "fees": truth_order.get("fees", "0"),
                "order_id": order_id,
                "client_order_id": client_order_id,
                "decision_id": decision_id,
            }
            
            try:
                portfolio_result = self._portfolio_sink.apply_fill(trade, idempotency_key=idempotency_key)
                portfolio_updated = portfolio_result.updated
                portfolio_ref = portfolio_result.ref
                
                # Append E3 PORTFOLIO_APPLY (success)
                portfolio_audit = {
                    "schema_version": "1.0.0",
                    "phase": "14E",
                    "event": "PORTFOLIO_APPLY",
                    "timestamp_ms": ts_ms,
                    "symbol": symbol,
                    "data": {
                        "portfolio_updated": portfolio_updated,
                        "portfolio_ref": portfolio_ref,
                        "idempotency_key": idempotency_key,
                        "decision_id": decision_id,
                    },
                }
                
                self._audit_store.append(portfolio_audit)
                audits_collected.append(portfolio_audit)
            
            except Exception as e:
                # Portfolio failure → ERROR (but ledger NOT reverted)
                error = SettlementError(
                    code="SETTLEMENT_003_PORTFOLIO_APPLY_FAILED",
                    message=f"Portfolio apply failed: {str(e)}",
                    details={"type": type(e).__name__},
                )
                error_dict = error.to_dict()
                settlement_status = "ERROR"
                
                # Append E3 PORTFOLIO_APPLY (failure)
                portfolio_audit = {
                    "schema_version": "1.0.0",
                    "phase": "14E",
                    "event": "PORTFOLIO_APPLY",
                    "timestamp_ms": ts_ms,
                    "symbol": symbol,
                    "data": {
                        "portfolio_updated": False,
                        "error": error_dict,
                        "idempotency_key": idempotency_key,
                        "decision_id": decision_id,
                    },
                }
                
                self._audit_store.append(portfolio_audit)
                audits_collected.append(portfolio_audit)
        
        elif terminal_status in ["REJECTED", "CANCELED"]:
            # Non-FILLED terminal → portfolio SKIPPED (NOT_APPLICABLE)
            portfolio_audit = {
                "schema_version": "1.0.0",
                "phase": "14E",
                "event": "PORTFOLIO_APPLY",
                "timestamp_ms": ts_ms,
                "symbol": symbol,
                "data": {
                    "portfolio_updated": False,
                    "skip_reason": "NOT_APPLICABLE",
                    "terminal_status": terminal_status,
                    "decision_id": decision_id,
                },
            }
            
            self._audit_store.append(portfolio_audit)
            audits_collected.append(portfolio_audit)
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 10: Append E4 SETTLEMENT_SUMMARY (always)
        # ─────────────────────────────────────────────────────────────────────────
        
        summary_audit = {
            "schema_version": "1.0.0",
            "phase": "14E",
            "event": "SETTLEMENT_SUMMARY",
            "timestamp_ms": ts_ms,
            "symbol": symbol,
            "data": {
                "settlement_status": settlement_status,
                "truth_source": truth_source,
                "terminal_status": terminal_status,
                "idempotency_key": idempotency_key,
                "ledger_ref": ledger_ref,
                "portfolio_updated": portfolio_updated,
                "decision_id": decision_id,
            },
        }
        
        if error_dict:
            summary_audit["data"]["error"] = error_dict
        
        self._audit_store.append(summary_audit)
        audits_collected.append(summary_audit)
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 11: Return SettlementResult
        # ─────────────────────────────────────────────────────────────────────────
        
        result = SettlementResult(
            status=settlement_status,
            ts_ms=ts_ms,
            decision_id=decision_id,
            client_order_id=client_order_id,
            order_id=order_id,
            symbol=symbol,
            truth_source=truth_source,
            terminal_status=terminal_status,
            idempotency_key=idempotency_key,
            already_applied=False,
            ledger_ref=ledger_ref,
            portfolio_updated=portfolio_updated,
            portfolio_ref=portfolio_ref,
            audits=audits_collected[:self._max_audits],
            error=error_dict,
        )
        
        return result.to_dict()
