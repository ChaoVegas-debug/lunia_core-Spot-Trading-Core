"""
EPOCH C: Orphan Position Guard (Component 6)
CAPITAL SAFETY: Detects unprotected positions and triggers Emergency Close

Safety Valve: Can bypass global_stop for reduce_only Emergency Close ONLY
under strict eligibility conditions (risk-reducing action).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# Deadline Policy Constants
ORPHAN_DEADLINE_SEC = 10  # Position must be protected within 10s of Entry fill


# Reason Codes (Machine-Readable)
class OrphanReasonCode:
    """Orphan Guard reason codes for audit trail"""
    ORPHAN_WITHIN_DEADLINE = "ORPHAN_WITHIN_DEADLINE"
    ORPHAN_DEADLINE_EXCEEDED = "ORPHAN_DEADLINE_EXCEEDED"
    SL_ACTIVE = "SL_ACTIVE"
    SL_MISSING = "SL_MISSING"
    ENTRY_NOT_FILLED = "ENTRY_NOT_FILLED"
    ENTRY_FILL_TS_UNKNOWN = "ENTRY_FILL_TS_UNKNOWN"
    SAFETY_VALVE_ALLOWED = "SAFETY_VALVE_ALLOWED"
    SAFETY_VALVE_NOT_ELIGIBLE = "SAFETY_VALVE_NOT_ELIGIBLE"
    GLOBAL_STOP_ACTIVE = "GLOBAL_STOP_ACTIVE"
    EMERGENCY_CLOSE_SUBMIT_FAILED = "EMERGENCY_CLOSE_SUBMIT_FAILED"
    EMERGENCY_CLOSE_IDEMPOTENT_RECONCILE = "EMERGENCY_CLOSE_IDEMPOTENT_RECONCILE"
    NO_POSITION_EXISTS = "NO_POSITION_EXISTS"
    POSITION_MISMATCH = "POSITION_MISMATCH"


class OrphanPositionGuard:
    """
    Orphan Position Guard
    
    Detects unprotected positions after Entry fill and triggers Emergency Close
    in REAL mode. Has Safety Valve to bypass global_stop for reduce_only closes.
    
    Policy:
    - Deadline: 10s after Entry FILLED/PARTIALLY_FILLED
    - Protection: SL must be ACTIVE (SUBMITTED/PARTIALLY_FILLED/FILLED)
    - Emergency Close: MARKET, reduce_only=True, opposite side
    - Idempotency: deterministic client_order_id
    """
    
    def evaluate_and_act(
        self,
        *,
        intent_id: str,
        plan: Dict[str, Any],
        order_executions: List[Dict[str, Any]],
        run_mode: str,
        governance_snapshot: Dict[str, Any],
        position_state: Dict[str, Any],
        now_utc: datetime,
        adapter: Optional[Any] = None,
        audit_emit: Callable[..., Any],
        sanitize_exchange_response: Callable[..., Any]
    ) -> Dict[str, Any]:
        """
        Evaluate orphan condition and act if needed
        
        Args:
            intent_id: Execution intent ID
            plan: Order plan dict (must have 'orders', 'plan_version', 'asset')
            order_executions: Latest order execution records
            run_mode: "dry" | "real"
            governance_snapshot: Governance state (global_stop, etc.)
            position_state: {'position_qty': float, 'entry_filled_qty': float, 'symbol': str}
            now_utc: Current UTC time
            adapter: Exchange adapter (required for REAL)
            audit_emit: Audit emission function
            sanitize_exchange_response: Exchange response sanitizer
        
        Returns:
            {
                "is_orphan": bool,
                "protected": bool,
                "decision": str,
                "reason_codes": List[str],
                "metadata": Dict[str, Any]
            }
        """
        reason_codes = []
        metadata = {}
        
        # Extract plan details
        orders = plan.get("orders", [])
        plan_version = plan.get("plan_version", 1)
        asset = plan.get("asset", "UNKNOWN")
        
        # Find Entry and SL orders
        entry_order = None
        sl_order = None
        
        for order in orders:
            order_type = order.get("order_type", "")
            if order_type == "ENTRY":
                entry_order = order
            elif order_type == "SL":
                sl_order = order
        
        if not entry_order:
            # No entry order - cannot have orphan
            return {
                "is_orphan": False,
                "protected": True,  # N/A but conservative
                "decision": "NOOP",
                "reason_codes": ["NO_ENTRY_ORDER"],
                "metadata": {}
            }
        
        # Find corresponding executions
        entry_exec = self._find_execution(order_executions, entry_order.get("client_order_id"))
        sl_exec = self._find_execution(order_executions, sl_order.get("client_order_id")) if sl_order else None
        
        # Check if Entry is filled
        entry_filled = entry_exec and entry_exec.get("status") in ["FILLED", "PARTIALLY_FILLED"]
        
        if not entry_filled:
            # Entry not filled - no orphan risk yet
            reason_codes.append(OrphanReasonCode.ENTRY_NOT_FILLED)
            return {
                "is_orphan": False,
                "protected": True,  # N/A
                "decision": "NOOP",
                "reason_codes": reason_codes,
                "metadata": {"entry_status": entry_exec.get("status") if entry_exec else "NOT_FOUND"}
            }
        
        # Entry is filled - check protection deadline
        entry_filled_at = entry_exec.get("filled_at")
        
        # Check SL protection status
        sl_active = sl_exec and sl_exec.get("status") in ["SUBMITTED", "PARTIALLY_FILLED", "FILLED"]
        
        if sl_active:
            # SL is active - position is protected
            reason_codes.append(OrphanReasonCode.SL_ACTIVE)
            return {
                "is_orphan": False,
                "protected": True,
                "decision": "NOOP",
                "reason_codes": reason_codes,
                "metadata": {"sl_status": sl_exec.get("status")}
            }
        
        # SL is missing or not active
        reason_codes.append(OrphanReasonCode.SL_MISSING)
        
        # Check deadline
        orphan_deadline_exceeded = False
        
        if entry_filled_at:
            # Parse timestamp
            if isinstance(entry_filled_at, str):
                try:
                    if entry_filled_at.endswith('Z'):
                        filled_dt = datetime.fromisoformat(entry_filled_at.replace('Z', '+00:00'))
                    else:
                        filled_dt = datetime.fromisoformat(entry_filled_at)
                    
                    age_sec = (now_utc - filled_dt).total_seconds()
                    metadata["entry_filled_age_sec"] = age_sec
                    
                    if age_sec <= ORPHAN_DEADLINE_SEC:
                        reason_codes.append(OrphanReasonCode.ORPHAN_WITHIN_DEADLINE)
                        orphan_deadline_exceeded = False
                    else:
                        reason_codes.append(OrphanReasonCode.ORPHAN_DEADLINE_EXCEEDED)
                        orphan_deadline_exceeded = True
                except (ValueError, TypeError):
                    # Invalid timestamp
                    reason_codes.append(OrphanReasonCode.ENTRY_FILL_TS_UNKNOWN)
                    orphan_deadline_exceeded = True  # Fail-closed conservative
            elif isinstance(entry_filled_at, datetime):
                age_sec = (now_utc - entry_filled_at).total_seconds()
                metadata["entry_filled_age_sec"] = age_sec
                
                if age_sec <= ORPHAN_DEADLINE_SEC:
                    reason_codes.append(OrphanReasonCode.ORPHAN_WITHIN_DEADLINE)
                    orphan_deadline_exceeded = False
                else:
                    reason_codes.append(OrphanReasonCode.ORPHAN_DEADLINE_EXCEEDED)
                    orphan_deadline_exceeded = True
            else:
                # Unknown timestamp type
                reason_codes.append(OrphanReasonCode.ENTRY_FILL_TS_UNKNOWN)
                orphan_deadline_exceeded = True  # Fail-closed conservative
        else:
            # No filled timestamp
            reason_codes.append(OrphanReasonCode.ENTRY_FILL_TS_UNKNOWN)
            orphan_deadline_exceeded = True  # Fail-closed conservative in REAL
        
        # Position is orphan if deadline exceeded
        is_orphan = orphan_deadline_exceeded
        
        if not is_orphan:
            # Still within deadline - not orphan yet
            return {
                "is_orphan": False,
                "protected": False,
                "decision": "NOOP",
                "reason_codes": reason_codes,
                "metadata": metadata
            }
        
        # ORPHAN DETECTED - need Emergency Close
        
        # Check idempotency - has Emergency Close already been attempted?
        emergency_client_order_id = f"{intent_id}:{plan_version}:EMERGENCY_CLOSE"
        existing_emergency = self._find_execution(order_executions, emergency_client_order_id)
        
        if existing_emergency:
            # Emergency Close already exists - idempotent reconcile
            reason_codes.append(OrphanReasonCode.EMERGENCY_CLOSE_IDEMPOTENT_RECONCILE)
            metadata["existing_emergency_status"] = existing_emergency.get("status")
            
            # Emit orphan detection audit (only once)
            audit_emit(
                event_type="ORPHAN_POSITION_DETECTED",
                intent_id=intent_id,
                plan_id=plan.get("id"),
                reason_codes=reason_codes,
                metadata=metadata
            )
            
            return {
                "is_orphan": True,
                "protected": False,
                "decision": "DETECTED",  # Already handled
                "reason_codes": reason_codes,
                "metadata": metadata
            }
        
        # DRY MODE - only detect and audit simulation
        if run_mode == "dry":
            # Emit simulation detection
            audit_emit(
                event_type="ORPHAN_POSITION_DETECTED_SIMULATION",
                intent_id=intent_id,
                plan_id=plan.get("id"),
                reason_codes=reason_codes,
                metadata=metadata
            )
            
            return {
                "is_orphan": True,
                "protected": False,
                "decision": "EMERGENCY_CLOSE_SIMULATED",
                "reason_codes": reason_codes,
                "metadata": metadata
            }
        
        # REAL MODE - attempt Emergency Close
        
        # Check Safety Valve eligibility
        global_stop = governance_snapshot.get("global_stop", False)
        
        if global_stop:
            reason_codes.append(OrphanReasonCode.GLOBAL_STOP_ACTIVE)
            metadata["global_stop"] = True
        
        # Safety Valve conditions:
        # 1. Position exists
        # 2. Emergency Close is reduce_only=True
        # 3. Quantity does not exceed position
        
        position_qty = position_state.get("position_qty", 0)
        entry_filled_qty = position_state.get("entry_filled_qty", 0)
        
        if abs(position_qty) == 0:
            # No position exists - cannot close
            reason_codes.append(OrphanReasonCode.NO_POSITION_EXISTS)
            reason_codes.append(OrphanReasonCode.SAFETY_VALVE_NOT_ELIGIBLE)
            
            # Audit blocked
            audit_emit(
                event_type="EMERGENCY_CLOSE_BLOCKED",
                intent_id=intent_id,
                plan_id=plan.get("id"),
                reason_codes=reason_codes,
                metadata=metadata
            )
            
            return {
                "is_orphan": True,
                "protected": False,
                "decision": "EMERGENCY_CLOSE_BLOCKED",
                "reason_codes": reason_codes,
                "metadata": metadata
            }
        
        # Calculate emergency close quantity
        qty_close = min(abs(position_qty), abs(entry_filled_qty))
        
        if qty_close == 0:
            # Position mismatch - fail-closed
            reason_codes.append(OrphanReasonCode.POSITION_MISMATCH)
            reason_codes.append(OrphanReasonCode.SAFETY_VALVE_NOT_ELIGIBLE)
            
            audit_emit(
                event_type="EMERGENCY_CLOSE_BLOCKED",
                intent_id=intent_id,
                plan_id=plan.get("id"),
                reason_codes=reason_codes,
                metadata=metadata
            )
            
            return {
                "is_orphan": True,
                "protected": False,
                "decision": "EMERGENCY_CLOSE_BLOCKED",
                "reason_codes": reason_codes,
                "metadata": metadata
            }
        
        # Determine side (opposite of Entry)
        entry_side = entry_order.get("side", "BUY")
        emergency_side = "SELL" if entry_side == "BUY" else "BUY"
        
        # Safety Valve is eligible
        if global_stop:
            reason_codes.append(OrphanReasonCode.SAFETY_VALVE_ALLOWED)
            metadata["safety_valve"] = "ACTIVE"
        
        # Emit orphan detection + emergency close triggered
        audit_emit(
            event_type="ORPHAN_POSITION_DETECTED",
            intent_id=intent_id,
            plan_id=plan.get("id"),
            reason_codes=reason_codes,
            metadata=metadata
        )
        
        audit_emit(
            event_type="EMERGENCY_CLOSE_TRIGGERED",
            intent_id=intent_id,
            plan_id=plan.get("id"),
            reason_codes=reason_codes,
            metadata={
                **metadata,
                "emergency_side": emergency_side,
                "emergency_qty": qty_close,
                "reduce_only": True,
                "client_order_id": emergency_client_order_id
            }
        )
        
        # Attempt adapter submission
        if not adapter:
            # No adapter - cannot submit (fail-closed)
            reason_codes.append(OrphanReasonCode.EMERGENCY_CLOSE_SUBMIT_FAILED)
            metadata["error"] = "No adapter provided"
            
            audit_emit(
                event_type="EMERGENCY_CLOSE_BLOCKED",
                intent_id=intent_id,
                plan_id=plan.get("id"),
                reason_codes=reason_codes,
                metadata=metadata
            )
            
            return {
                "is_orphan": True,
                "protected": False,
                "decision": "EMERGENCY_CLOSE_BLOCKED",
                "reason_codes": reason_codes,
                "metadata": metadata
            }
        
        # Submit Emergency Close
        try:
            response = adapter.submit_order(
                symbol=asset,
                side=emergency_side,
                quantity=qty_close,
                order_type="MARKET",
                reduce_only=True,
                client_order_id=emergency_client_order_id
            )
            
            # Success - emit submitted audit
            audit_emit(
                event_type="EMERGENCY_CLOSE_SUBMITTED",
                intent_id=intent_id,
                plan_id=plan.get("id"),
                reason_codes=reason_codes,
                exchange_response=sanitize_exchange_response(response),
                metadata={
                    **metadata,
                    "emergency_qty": qty_close,
                    "emergency_side": emergency_side
                }
            )
            
            return {
                "is_orphan": True,
                "protected": False,
                "decision": "EMERGENCY_CLOSE_SUBMITTED",
                "reason_codes": reason_codes,
                "metadata": {
                    **metadata,
                    "exchange_response": sanitize_exchange_response(response)
                }
            }
            
        except Exception as e:
            # Submission failed
            reason_codes.append(OrphanReasonCode.EMERGENCY_CLOSE_SUBMIT_FAILED)
            metadata["error"] = str(e)
            
            audit_emit(
                event_type="EMERGENCY_CLOSE_BLOCKED",
                intent_id=intent_id,
                plan_id=plan.get("id"),
                reason_codes=reason_codes,
                metadata=metadata
            )
            
            return {
                "is_orphan": True,
                "protected": False,
                "decision": "EMERGENCY_CLOSE_BLOCKED",
                "reason_codes": reason_codes,
                "metadata": metadata
            }
    
    def _find_execution(
        self,
        order_executions: List[Dict[str, Any]],
        client_order_id: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Find execution by client_order_id"""
        if not client_order_id:
            return None
        
        for exec_record in order_executions:
            if exec_record.get("client_order_id") == client_order_id:
                return exec_record
        
        return None
