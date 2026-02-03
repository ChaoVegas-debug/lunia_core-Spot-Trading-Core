"""
PHASE 14C — EXECUTION ROUTER: The Single Chokepoint

Orchestrates gateway (14A decision) → client (14B execution).

CRITICAL GOVERNANCE:
- Single chokepoint (only legal path decision → execution)
- Defense-in-depth (double kill switch)
- Audit binding (decision ↔ client_order_id ↔ order_id)
- Fail-closed (never crash, always audit)
- Deterministic (no wall-clock, stable JSON)
- Hands not brain (no trading logic)

DANGER: This is the ONLY legal path to real execution.
Bypass = system compromise.
"""

import hashlib
from decimal import Decimal
from typing import Dict, Any, Optional, Callable

from .models import RoutingResult, RoutingStatus, RoutingError, stable_json, derive_decision_id

# Import gateway contracts (14A)
from extensions.execution_gateway.airlock import ExecutionGateway
from extensions.execution_gateway.models import (
    ExecutionRequest,
    ExecutionContextSnapshot,
    ExecutionDecision,
    AuditPayload,
    canonical_ts,
    normalize_symbol,
)

# Import execution client contracts (14B)
from extensions.exchange_connectivity.execution_client import BinanceExecutionClient
from extensions.exchange_connectivity.trade_models import (
    OrderResult,
    generate_client_order_id,
)

# Import audit store
from extensions.genome_dsl.audit_store import AuditStore


# ────────────────────────────────────────────────────────────────────────────────
# EXECUTION ROUTER (THE NERVOUS SYSTEM)
# ────────────────────────────────────────────────────────────────────────────────

class ExecutionRouter:
    """
    Execution Router: Single chokepoint from decision → execution.
    
    Orchestration flow (STRICT ORDER):
    1. Normalize symbol (fail-closed)
    2. Gateway evaluation (permission)
    3. If BLOCKED → stop (client never called)
    4. Defense-in-depth kill switch re-check
    5. Map intent → execution params
    6. Execute client.create_order()
    7. Audit binding (decision ↔ order)
    8. Return RoutingResult
    
    Governance:
    - No bypass: client callable ONLY after gateway ALLOWED
    - Double kill switch: router re-checks even if gateway allowed
    - Fail-closed: errors produce safe results with audits
    - Deterministic: no wall-clock, stable JSON
    """
    
    def __init__(
        self,
        gateway: ExecutionGateway,
        client: BinanceExecutionClient,
        audit_store: AuditStore,
        *,
        symbol_normalizer: Optional[Callable[[str], str]] = None,
        max_audits: int = 10,
        test_mode: bool = True,  # Conservative default (sandbox)
    ):
        """
        Initialize execution router.
        
        Args:
            gateway: ExecutionGateway (Phase 14A)
            client: BinanceExecutionClient (Phase 14B)
            audit_store: AuditStore (audit persistence)
            symbol_normalizer: Optional symbol normalizer (default: use gateway's)
            max_audits: Max audits to include in result (bounded)
            test_mode: If True, use test endpoint (no real execution)
        """
        self._gateway = gateway
        self._client = client
        self._audit_store = audit_store
        self._symbol_normalizer = symbol_normalizer or normalize_symbol
        self._max_audits = max_audits
        self._test_mode = test_mode
    
    def route(
        self,
        request: ExecutionRequest,
        *,
        context: Optional[ExecutionContextSnapshot] = None,
    ) -> Dict[str, Any]:
        """
        Route execution request (THE SINGLE CHOKEPOINT).
        
        Args:
            request: ExecutionRequest (intent + symbol + ts)
            context: ExecutionContextSnapshot (snapshot + portfolio + health)
        
        Returns:
            RoutingResult as dict (never throws)
        
        Algorithm (STRICT ORDER, FAIL-FAST):
        1. Normalize symbol
        2. Gateway evaluation (permission)
        3. If BLOCKED → stop
        4. Defense-in-depth kill switch re-check
        5. Map intent → execution params
        6. Execute
        7. Audit binding
        8. Return
        """
        audits_collected = []
        
        try:
            return self._route_internal(request, context, audits_collected)
        except Exception as e:
            # Unexpected exception → fail-closed ERROR
            error = RoutingError(
                code="ROUTER_000",
                message=f"Unexpected router error: {str(e)}",
                details={"type": type(e).__name__},
            )
            
            # Create minimal safe result
            result = RoutingResult(
                status="ERROR",
                ts_ms=request.ts_ms,
                decision={"status": "BLOCKED", "reason_code": "ROUTER_000"},
                decision_id=None,
                client_order_id=None,
                order_result=None,
                audits=audits_collected[:self._max_audits],
                error=error.to_dict(),
            )
            
            return result.to_dict()
    
    def _route_internal(
        self,
        request: ExecutionRequest,
        context: Optional[ExecutionContextSnapshot],
        audits_collected: list,
    ) -> Dict[str, Any]:
        """
        Internal routing logic (fail-fast hierarchy).
        
        This method assumes caller catches exceptions.
        """
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 1: Normalize symbol (fail-closed)
        # ─────────────────────────────────────────────────────────────────────────
        
        try:
            normalized_symbol = self._symbol_normalizer(request.symbol)
        except Exception as e:
            error = RoutingError(
                code="ROUTER_001_SYMBOL_INVALID",
                message=f"Symbol normalization failed: {str(e)}",
                details={"raw_symbol": request.symbol},
            )
            
            result = RoutingResult(
                status="ERROR",
                ts_ms=request.ts_ms,
                decision={"status": "BLOCKED", "reason_code": "ROUTER_001_SYMBOL_INVALID"},
                decision_id=None,
                client_order_id=None,
                audits=audits_collected[:self._max_audits],
                error=error.to_dict(),
            )
            
            return result.to_dict()
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 2: Gateway Evaluation (PERMISSION)
        # ─────────────────────────────────────────────────────────────────────────
        
        try:
            decision, gateway_audit = self._gateway.evaluate(request, context)
        except Exception as e:
            # Gateway exception → fail-closed ERROR
            error = RoutingError(
                code="ROUTER_002_GATEWAY_EXCEPTION",
                message=f"Gateway evaluation failed: {str(e)}",
                details={"type": type(e).__name__},
            )
            
            result = RoutingResult(
                status="ERROR",
                ts_ms=request.ts_ms,
                decision={"status": "BLOCKED", "reason_code": "ROUTER_002_GATEWAY_EXCEPTION"},
                decision_id=None,
                client_order_id=None,
                audits=audits_collected[:self._max_audits],
                error=error.to_dict(),
            )
            
            return result.to_dict()
        
        # Append gateway audit (AUDIT A)
        gateway_audit_dict = gateway_audit.to_dict()
        self._audit_store.append(gateway_audit_dict)
        audits_collected.append(gateway_audit_dict)
        
        # Convert decision to dict
        decision_dict = decision.to_dict()
        
        # Derive decision_id
        decision_id = derive_decision_id(gateway_audit_dict, decision_dict)
        
        # Canonical timestamp
        ts_ms = canonical_ts(
            request.ts_ms,
            decision.ts_ms,
            context.ts_ms if context else None,
        )
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 3: If BLOCKED → Stop (CLIENT NEVER CALLED)
        # ─────────────────────────────────────────────────────────────────────────
        
        if decision.status == "BLOCKED":
            # Create router audit (AUDIT B)
            router_audit = {
                "schema_version": "1.0.0",
                "phase": "14C",
                "event": "ROUTER_ROUTE_RESULT",
                "timestamp_ms": ts_ms,
                "symbol": normalized_symbol,
                "data": {
                    "status": "BLOCKED",
                    "decision_id": decision_id,
                    "reason_code": decision.reason_code,
                    "reason_message": decision.reason_message,
                },
            }
            
            self._audit_store.append(router_audit)
            audits_collected.append(router_audit)
            
            result = RoutingResult(
                status="BLOCKED",
                ts_ms=ts_ms,
                decision=decision_dict,
                decision_id=decision_id,
                client_order_id=None,
                order_result=None,
                audits=audits_collected[:self._max_audits],
                error=None,
            )
            
            return result.to_dict()
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 4: Defense-in-Depth Kill Switch Re-Check
        # ─────────────────────────────────────────────────────────────────────────
        
        # Re-check kill switch (second gate)
        if self._gateway._kill_switch.enabled:
            # Kill switch enabled → BLOCK execution
            router_audit = {
                "schema_version": "1.0.0",
                "phase": "14C",
                "event": "ROUTER_ROUTE_RESULT",
                "timestamp_ms": ts_ms,
                "symbol": normalized_symbol,
                "data": {
                    "status": "BLOCKED",
                    "decision_id": decision_id,
                    "reason_code": "KILL_SWITCH_RERAISED",
                    "reason_message": f"Kill switch enabled at second gate: {self._gateway._kill_switch.reason}",
                    "defense_in_depth": True,
                },
            }
            
            self._audit_store.append(router_audit)
            audits_collected.append(router_audit)
            
            result = RoutingResult(
                status="BLOCKED",
                ts_ms=ts_ms,
                decision=decision_dict,
                decision_id=decision_id,
                client_order_id=None,
                order_result=None,
                audits=audits_collected[:self._max_audits],
                error=None,
            )
            
            return result.to_dict()
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 5: Map Intent → Execution Params (fail-closed)
        # ─────────────────────────────────────────────────────────────────────────
        
        try:
            execution_params = self._map_intent_to_params(
                request.intent,
                normalized_symbol,
                ts_ms or 0,
            )
        except Exception as e:
            # Mapping failed → fail-closed ERROR
            error = RoutingError(
                code="ROUTER_003_MAPPING_FAILED",
                message=f"Intent mapping failed: {str(e)}",
                details={"intent_signal": request.intent.get("signal")},
            )
            
            router_audit = {
                "schema_version": "1.0.0",
                "phase": "14C",
                "event": "ROUTER_ROUTE_RESULT",
                "timestamp_ms": ts_ms,
                "symbol": normalized_symbol,
                "data": {
                    "status": "ERROR",
                    "decision_id": decision_id,
                    "error": error.to_dict(),
                },
            }
            
            self._audit_store.append(router_audit)
            audits_collected.append(router_audit)
            
            result = RoutingResult(
                status="ERROR",
                ts_ms=ts_ms,
                decision=decision_dict,
                decision_id=decision_id,
                client_order_id=None,
                order_result=None,
                audits=audits_collected[:self._max_audits],
                error=error.to_dict(),
            )
            
            return result.to_dict()
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 6: Execute (single attempt, no retries)
        # ─────────────────────────────────────────────────────────────────────────
        
        try:
            order_result = self._client.create_order(
                symbol=normalized_symbol,
                side=execution_params["side"],
                order_type=execution_params["order_type"],
                quantity=execution_params["quantity"],
                price=execution_params.get("price"),
                client_order_id=execution_params["client_order_id"],
                test_mode=self._test_mode,
            )
        except Exception as e:
            # Client exception → fail-safe PARTIAL_FAILURE
            error = RoutingError(
                code="ROUTER_004_CLIENT_EXCEPTION",
                message=f"Execution client raised exception: {str(e)}",
                details={"type": type(e).__name__},
            )
            
            # Create router audit (AUDIT B)
            router_audit = {
                "schema_version": "1.0.0",
                "phase": "14C",
                "event": "ROUTER_ROUTE_RESULT",
                "timestamp_ms": ts_ms,
                "symbol": normalized_symbol,
                "data": {
                    "status": "PARTIAL_FAILURE",
                    "decision_id": decision_id,
                    "client_order_id": execution_params["client_order_id"],
                    "error": error.to_dict(),
                },
            }
            
            self._audit_store.append(router_audit)
            audits_collected.append(router_audit)
            
            # Create execution error audit (AUDIT C)
            execution_audit = {
                "schema_version": "1.0.0",
                "phase": "14C",
                "event": "EXECUTION_RESULT",
                "timestamp_ms": ts_ms,
                "symbol": normalized_symbol,
                "data": {
                    "decision_id": decision_id,
                    "client_order_id": execution_params["client_order_id"],
                    "order_id": None,
                    "status": "UNKNOWN",
                    "error": error.to_dict(),
                },
            }
            
            self._audit_store.append(execution_audit)
            audits_collected.append(execution_audit)
            
            result = RoutingResult(
                status="PARTIAL_FAILURE",
                ts_ms=ts_ms,
                decision=decision_dict,
                decision_id=decision_id,
                client_order_id=execution_params["client_order_id"],
                order_result={"status": "UNKNOWN", "error": str(e)},
                audits=audits_collected[:self._max_audits],
                error=error.to_dict(),
            )
            
            return result.to_dict()
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 7: Audit Binding (decision ↔ client_order_id ↔ order_id)
        # ─────────────────────────────────────────────────────────────────────────
        
        order_result_dict = order_result.to_dict()
        
        # Create execution audit (AUDIT C)
        execution_audit = {
            "schema_version": "1.0.0",
            "phase": "14C",
            "event": "EXECUTION_RESULT",
            "timestamp_ms": ts_ms,
            "symbol": normalized_symbol,
            "data": {
                "decision_id": decision_id,
                "client_order_id": order_result.client_order_id,
                "order_id": order_result.order_id,
                "status": order_result.status,
                "filled_qty": str(order_result.filled_qty),
                "avg_price": str(order_result.avg_price),
                "fees": str(order_result.fees),
            },
        }
        
        self._audit_store.append(execution_audit)
        audits_collected.append(execution_audit)
        
        # Create router audit (AUDIT B)
        router_audit = {
            "schema_version": "1.0.0",
            "phase": "14C",
            "event": "ROUTER_ROUTE_RESULT",
            "timestamp_ms": ts_ms,
            "symbol": normalized_symbol,
            "data": {
                "status": "SUCCESS",
                "decision_id": decision_id,
                "client_order_id": order_result.client_order_id,
                "order_id": order_result.order_id,
                "order_status": order_result.status,
            },
        }
        
        self._audit_store.append(router_audit)
        audits_collected.append(router_audit)
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 8: Return RoutingResult
        # ─────────────────────────────────────────────────────────────────────────
        
        result = RoutingResult(
            status="SUCCESS",
            ts_ms=ts_ms,
            decision=decision_dict,
            decision_id=decision_id,
            client_order_id=order_result.client_order_id,
            order_result=order_result_dict,
            audits=audits_collected[:self._max_audits],
            error=None,
        )
        
        return result.to_dict()
    
    def _map_intent_to_params(
        self,
        intent: Dict[str, Any],
        symbol: str,
        timestamp_ms: int,
    ) -> Dict[str, Any]:
        """
        Map strategy intent → execution parameters (fail-closed).
        
        This is a direct translation, NOT trading logic.
        
        Args:
            intent: Strategy intent dict
            symbol: Normalized symbol
            timestamp_ms: Timestamp for client_order_id
        
        Returns:
            Execution params dict
        
        Raises:
            ValueError: If mapping fails (missing fields)
        """
        # Extract virtual_order (fail-closed if missing)
        virtual_order = intent.get("virtual_order")
        if not virtual_order:
            raise ValueError("Intent missing 'virtual_order' field")
        
        # Map side
        side_raw = virtual_order.get("side", "").upper()
        if side_raw not in ["BUY", "SELL"]:
            raise ValueError(f"Invalid or missing side: {side_raw}")
        
        # Map order_type (default to MARKET if not specified)
        price_type = virtual_order.get("price_type", "IMMEDIATE_FILL").upper()
        if "LIMIT" in price_type:
            order_type = "LIMIT"
        else:
            order_type = "MARKET"
        
        # Get fill_price
        fill_price_raw = virtual_order.get("fill_price")
        if not fill_price_raw:
            raise ValueError("Intent missing 'fill_price'")
        
        fill_price = Decimal(str(fill_price_raw))
        
        # Get quantity (default to conservative 0.001 if missing)
        # This is NOT trading logic; it's a fail-safe default
        quantity_raw = virtual_order.get("quantity", "0.001")
        quantity = Decimal(str(quantity_raw))
        
        # Generate deterministic client_order_id
        client_order_id = generate_client_order_id(
            symbol,
            timestamp_ms,
            nonce=intent.get("signal", ""),
        )
        
        # Build params
        params = {
            "side": side_raw,
            "order_type": order_type,
            "quantity": quantity,
            "client_order_id": client_order_id,
        }
        
        # Add price for LIMIT orders
        if order_type == "LIMIT":
            params["price"] = fill_price
        
        return params
