"""
EPOCH C: Execution API Endpoints
/api/execution/intents/{id}/validate
/api/execution/intents/{id}/plan
/api/execution/intents/{id}/queue
/api/execution/intents/{id}
/api/execution/intents/{id}/audit
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from flask import Flask, jsonify, request
from sqlalchemy.orm import Session

from ..auth.database import get_session
from ..auth.rbac import current_user, require_role
from .governance_gate import ExecutionGovernanceGate
from .snapshots import capture_execution_snapshot, validate_snapshot_completeness
from .audit import emit_execution_audit, AuditEventType
from .converter import convert_intent_to_plan
from .orchestrator import enqueue_plan
from .models import OrderPlan, ExecutionAuditEvent
from ...proposal.models import ExecutionIntent

logger = logging.getLogger(__name__)


def register_execution_endpoints(app: Flask, require_role_func):
    """Register EPOCH C execution endpoints"""
    
    @app.post("/api/execution/intents/<intent_id>/validate")
    @require_role_func("TRADER", "ADMIN")
    def validate_intent(intent_id: str) -> tuple[Any, int]:
        """
        POST /api/execution/intents/{id}/validate
        
        Runs governance gate + guards + snapshot
        Returns: ALLOW / BLOCK with reason codes
        """
        with get_session() as session:
            # Load intent
            intent = session.query(ExecutionIntent).filter_by(id=intent_id).first()
            if not intent:
                return jsonify({"error": "Intent not found", "veto_codes": ["INTENT_NOT_FOUND"]}), 404
            
            # Get request payload (optional market/portfolio data)
            payload = request.get_json(force=True) or {}
            market_data = payload.get("market_data")
            portfolio = payload.get("portfolio")
            exchange_health = payload.get("exchange_health")
            run_mode = payload.get("run_mode", intent.run_mode or "dry")
            
            # Governance gate check
            gate = ExecutionGovernanceGate()
            decision = gate.check(
                run_mode=run_mode,
                market_data=market_data,
                portfolio=portfolio,
                exchange_health=exchange_health
            )
            
            # Capture snapshot
            snapshot = capture_execution_snapshot(
                run_mode=run_mode,
                governance_snapshot=decision.governance_snapshot,
                market_data=market_data,
                portfolio=portfolio,
                exchange_health=exchange_health
            )
            
            # Emit audit
            event_type = (AuditEventType.INTENT_VALIDATED 
                         if decision.decision == "ALLOW" 
                         else AuditEventType.INTENT_BLOCKED)
            
            emit_execution_audit(
                session=session,
                event_type=event_type,
                intent_id=intent_id,
                reason_codes=decision.reason_codes,
                metadata={
                    "decision": decision.decision,
                    "snapshot": snapshot
                }
            )
            
            session.commit()
            
            # Response
            if decision.decision != "ALLOW":
                return jsonify({
                    "decision": decision.decision,
                    "veto_codes": decision.reason_codes,
                    "governance_snapshot": decision.governance_snapshot,
                    "metadata": decision.metadata
                }), 403 if decision.decision == "BLOCK" else 409
            
            return jsonify({
                "decision": "ALLOW",
                "snapshot": snapshot,
                "governance_snapshot": decision.governance_snapshot
            }), 200
    
    @app.post("/api/execution/intents/<intent_id>/plan")
    @require_role_func("TRADER", "ADMIN")
    def create_plan(intent_id: str) -> tuple[Any, int]:
        """
        POST /api/execution/intents/{id}/plan
        
        Deterministic conversion + canonicalization + plan_hash
        Returns: OrderPlan with plan_hash
        """
        with get_session() as session:
            # Load intent
            intent = session.query(ExecutionIntent).filter_by(id=intent_id).first()
            if not intent:
                return jsonify({"error": "Intent not found", "veto_codes": ["INTENT_NOT_FOUND"]}), 404
            
            # Get conversion inputs
            payload = request.get_json(force=True) or {}
            approval_snapshot = payload.get("approval_snapshot", {
                "asset": intent.asset,
                "action": intent.action
            })
            execution_snapshot = payload.get("execution_snapshot", {
                "governance": {"run_mode": intent.run_mode or "dry"},
                "market_data": payload.get("market_data", {}),
                "portfolio": payload.get("portfolio", {})
            })
            
            # Convert to plan
            try:
                plan = convert_intent_to_plan(
                    intent=intent,
                    approval_snapshot=approval_snapshot,
                    execution_snapshot=execution_snapshot
                )
            except Exception as e:
                emit_execution_audit(
                    session=session,
                    event_type=AuditEventType.EXECUTION_FAILED,
                    intent_id=intent_id,
                    reason_codes=["CONVERSION_FAILED"],
                    metadata={"error": str(e)}
                )
                session.commit()
                return jsonify({
                    "error": "Plan conversion failed",
                    "veto_codes": ["CONVERSION_FAILED"],
                    "details": str(e)
                }), 400
            
            # Persist plan
            session.add(plan)
            
            # Emit audit
            emit_execution_audit(
                session=session,
                event_type=AuditEventType.ORDERPLAN_CREATED,
                intent_id=intent_id,
                plan_id=plan.id,
                plan_hash=plan.plan_hash,
                metadata={
                    "orders_count": len(plan.orders),
                    "total_notional_usd": sum(o.get("notional_usd", 0) for o in plan.orders)
                }
            )
            
            session.commit()
            
            return jsonify({
                "plan_id": plan.id,
                "plan_hash": plan.plan_hash,
                "orders_count": len(plan.orders),
                "status": "CREATED"
            }), 201
    
    @app.post("/api/execution/intents/<intent_id>/queue")
    @require_role_func("TRADER", "ADMIN")
    def queue_intent(intent_id: str) -> tuple[Any, int]:
        """
        POST /api/execution/intents/{id}/queue
        
        Requires READY + PLAN present; enqueues (idempotent)
        Returns: Queue position
        """
        with get_session() as session:
            # Load intent
            intent = session.query(ExecutionIntent).filter_by(id=intent_id).first()
            if not intent:
                return jsonify({"error": "Intent not found", "veto_codes": ["INTENT_NOT_FOUND"]}), 404
            
            # Check if plan exists
            plan = session.query(OrderPlan).filter_by(intent_id=intent_id).first()
            if not plan:
                return jsonify({
                    "error": "No plan found for intent",
                    "veto_codes": ["PLAN_NOT_FOUND"]
                }), 400
            
            # Re-check governance (authoritative)
            payload = request.get_json(force=True) or {}
            run_mode = payload.get("run_mode", intent.run_mode or "dry")
            
            gate = ExecutionGovernanceGate()
            decision = gate.check(
                run_mode=run_mode,
                market_data=payload.get("market_data"),
                portfolio=payload.get("portfolio"),
                exchange_health=payload.get("exchange_health")
            )
            
            if decision.decision != "ALLOW":
                emit_execution_audit(
                    session=session,
                    event_type=AuditEventType.INTENT_BLOCKED,
                    intent_id=intent_id,
                    plan_id=plan.id,
                    reason_codes=decision.reason_codes,
                    metadata={"stage": "queue", "decision": decision.decision}
                )
                session.commit()
                
                return jsonify({
                    "error": "Governance blocked queue",
                    "veto_codes": decision.reason_codes,
                    "governance_snapshot": decision.governance_snapshot
                }), 403
            
            # Enqueue (idempotent)
            try:
                queue_item = enqueue_plan(session, plan.id)
            except Exception as e:
                emit_execution_audit(
                    session=session,
                    event_type=AuditEventType.EXECUTION_FAILED,
                    intent_id=intent_id,
                    plan_id=plan.id,
                    reason_codes=["ENQUEUE_FAILED"],
                    metadata={"error": str(e)}
                )
                session.commit()
                return jsonify({
                    "error": "Enqueue failed",
                    "veto_codes": ["ENQUEUE_FAILED"],
                    "details": str(e)
                }), 500
            
            # Emit audit
            emit_execution_audit(
                session=session,
                event_type=AuditEventType.INTENT_QUEUED,
                intent_id=intent_id,
                plan_id=plan.id,
                metadata={
                    "queue_id": queue_item.id,
                    "priority": queue_item.priority,
                    "status": queue_item.status
                }
            )
            
            session.commit()
            
            return jsonify({
                "queue_id": queue_item.id,
                "plan_id": plan.id,
                "status": "QUEUED",
                "priority": queue_item.priority
            }), 201
    
    @app.get("/api/execution/intents/<intent_id>")
    @require_role_func("TRADER", "ADMIN")
    def get_intent_status(intent_id: str) -> tuple[Any, int]:
        """
        GET /api/execution/intents/{id}
        
        Returns: Intent + Plan + Execution status
        """
        with get_session() as session:
            intent = session.query(ExecutionIntent).filter_by(id=intent_id).first()
            if not intent:
                return jsonify({"error": "Intent not found"}), 404
            
            plan = session.query(OrderPlan).filter_by(intent_id=intent_id).first()
            
            response = {
                "intent_id": intent.id,
                "asset": intent.asset,
                "action": intent.action,
                "size_usd": intent.execution_params.get("size_usd") if intent.execution_params else None,
                "run_mode": intent.run_mode,
                "status": intent.status,
                "created_at": intent.created_at.isoformat() if intent.created_at else None,
                "plan": None,
                "execution": None
            }
            
            if plan:
                response["plan"] = {
                    "plan_id": plan.id,
                    "plan_hash": plan.plan_hash,
                    "orders_count": len(plan.orders),
                    "status": plan.status,
                    "created_at": plan.created_at.isoformat() if plan.created_at else None
                }
                
                # TODO: Add execution status from order_executions table
                # For now, simplified
                response["execution"] = {
                    "status": "PENDING"  # Would query order_executions
                }
            
            return jsonify(response), 200
    
    @app.get("/api/execution/intents/<intent_id>/audit")
    @require_role_func("TRADER", "ADMIN")
    def get_audit_trail(intent_id: str) -> tuple[Any, int]:
        """
        GET /api/execution/intents/{id}/audit
        
        Returns: Full append-only audit trail
        """
        with get_session() as session:
            # Check intent exists
            intent = session.query(ExecutionIntent).filter_by(id=intent_id).first()
            if not intent:
                return jsonify({"error": "Intent not found"}), 404
            
            # Get all audit events
            events = session.query(ExecutionAuditEvent).filter_by(
                intent_id=intent_id
            ).order_by(ExecutionAuditEvent.timestamp.asc()).all()
            
            trail = []
            for event in events:
                trail.append({
                    "id": event.id,
                    "event_type": event.event_type,
                    "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                    "plan_id": event.order_plan_id,
                    "order_execution_id": event.order_execution_id,
                    "worker_id": event.worker_id,
                    "reason_codes": event.reason_codes,
                    "plan_hash": event.plan_hash,
                    "intent_hash": event.intent_hash,
                    "metadata": event.metadata
                })
            
            return jsonify({
                "intent_id": intent_id,
                "events_count": len(trail),
                "trail": trail
            }), 200
