"""
EPOCH B: Proposal Domain API Endpoints
Wired into flask_app.py
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from flask import Flask, jsonify, request
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..auth.database import get_session
from ..auth.rbac import current_user
from .flask_app import _audit, safety_guard, OPS_TOKEN
from ..proposal.models import Proposal, ExecutionIntent, ProposalAuditEvent, ProposalStatus, ProposalAuditEventType
from ..proposal.schemas import (
    ProposalCreate, ApprovalRequest, RejectionRequest, RequestChangesRequest,
    GhostTestRequest
)
from ..proposal.governance import ProposalGovernanceValidator, GovernanceVetoError
from ...core.engine.ghost import GhostEngine

ghost_engine = GhostEngine()
logger = __import__("logging").getLogger(__name__)


def register_proposal_endpoints(app: Flask, require_role):
    """Register all 8 EPOCH B proposal endpoints."""
    
    @app.get("/api/proposals")
    @require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
    def list_proposals() -> Any:
        """List proposals with filters and pagination."""
        session: Session = get_session()
        try:
            status_filter = request.args.get("status")
            asset_filter = request.args.get("asset")
            risk_label_filter = request.args.get("risk_label")
            min_priority = request.args.get("min_priority", type=int)
            page = max(1, request.args.get("page", 1, type=int))
            page_size = min(100, max(1, request.args.get("page_size", 20, type=int)))
            
            query = session.query(Proposal)
            
            if status_filter:
                query = query.filter(Proposal.status == status_filter)
            if asset_filter:
                query = query.filter(Proposal.asset == asset_filter)
            if risk_label_filter:
                query = query.filter(Proposal.risk_label == risk_label_filter)
            if min_priority is not None:
                query = query.filter(Proposal.priority_score >= min_priority)
            
            total = query.count()
            proposals = query.order_by(
                Proposal.priority_score.desc(),
                Proposal.created_at.desc()
            ).offset((page - 1) * page_size).limit(page_size).all()
            
            items = []
            for p in proposals:
                items.append({
                    "id": p.id,
                    "version": p.version,
                    "status": p.status.value,
                    "asset": p.asset,
                    "action": p.action.value,
                    "risk_label": p.risk_label.value,
                    "priority_score": p.priority_score,
                    "confidence_score": p.confidence_score,
                    "thesis_summary": p.thesis_summary,
                    "created_at": p.created_at.isoformat(),
                    "expires_at": p.expires_at.isoformat() if p.expires_at else None
                })
            
            return jsonify({
                "proposals": items,
                "total": total,
                "page": page,
                "page_size": page_size
            })
        finally:
            session.close()
    
    
    @app.get("/api/proposals/<id>")
    @require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
    def get_proposal(id: str) -> Any:
        """Get full proposal detail."""
        session: Session = get_session()
        try:
            proposal = session.query(Proposal).filter(Proposal.id == id).first()
            if not proposal:
                return jsonify({"error": "Proposal not found"}), 404
            
            return jsonify({
                "id": proposal.id,
                "version": proposal.version,
                "status": proposal.status.value,
                "asset": proposal.asset,
                "action": proposal.action.value,
                "horizon": proposal.horizon.value,
                "risk_label": proposal.risk_label.value,
                "priority_score": proposal.priority_score,
                "governance_snapshot": proposal.governance_snapshot,
                "thesis_summary": proposal.thesis_summary,
                "thesis_dna": proposal.thesis_dna,
                "invalidation_rules": proposal.invalidation_rules,
                "factor_attribution": proposal.factor_attribution,
                "model_votes": proposal.model_votes,
                "confidence_score": proposal.confidence_score,
                "devils_advocate": proposal.devils_advocate,
                "execution_plan_preview": proposal.execution_plan_preview,
                "created_at": proposal.created_at.isoformat(),
                "updated_at": proposal.updated_at.isoformat(),
                "expires_at": proposal.expires_at.isoformat() if proposal.expires_at else None,
                "supersedes_id": proposal.supersedes_id,
                "created_by_user_id": proposal.created_by_user_id,
                "approved_by_user_id": proposal.approved_by_user_id,
                "rejected_by_user_id": proposal.rejected_by_user_id,
                "approved_at": proposal.approved_at.isoformat() if proposal.approved_at else None,
                "rejected_at": proposal.rejected_at.isoformat() if proposal.rejected_at else None,
                "rejection_reason": proposal.rejection_reason
            })
        finally:
            session.close()
    
    
    @app.post("/api/proposals")
    @require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
    def create_proposal() -> Any:
        """Create new proposal with validation."""
        try:
            payload = ProposalCreate.parse_obj(request.get_json(force=True) or {})
        except ValidationError as exc:
            return jsonify({"error": "Validation failed", "details": exc.errors()}), 400
        
        session: Session = get_session()
        try:
            governance_snapshot = ProposalGovernanceValidator.capture_creation_snapshot()
            
            proposal = Proposal(
                status=ProposalStatus.DRAFT,
                asset=payload.asset,
                action=payload.action,
                horizon=payload.horizon,
                risk_label=payload.risk_label,
                priority_score=payload.priority_score,
                governance_snapshot=governance_snapshot,
                thesis_summary=payload.thesis_summary,
                thesis_dna=payload.thesis_dna.dict(),
                invalidation_rules=payload.invalidation_rules,
                factor_attribution=[f.dict() for f in payload.factor_attribution],
                model_votes=payload.model_votes,
                confidence_score=payload.confidence_score,
                devils_advocate=payload.devils_advocate,
                execution_plan_preview=payload.execution_plan_preview.dict() if payload.execution_plan_preview else None,
                expires_at=datetime.fromisoformat(payload.expires_at) if payload.expires_at else None,
                created_by_user_id=current_user().get("id") if current_user() else None
            )
            
            session.add(proposal)
            session.flush()
            
            audit_event = ProposalAuditEvent(
                proposal_id=proposal.id,
                event_type=ProposalAuditEventType.PROPOSAL_CREATED,
                actor_user_id=current_user().get("id") if current_user() else None,
                actor_role=current_user().get("role") if current_user() else None,
                governance_snapshot=governance_snapshot,
                confidence_score_at_decision=proposal.confidence_score,
                data_freshness_state_at_decision=governance_snapshot.get("data_freshness_state"),
                event_metadata={"source": "API"}
            )
            session.add(audit_event)
            session.commit()
            
            return jsonify({"id": proposal.id, "status": proposal.status.value}), 201
        except Exception as e:
            session.rollback()
            logger.error(f"Error creating proposal: {e}")
            return jsonify({"error": str(e)}), 500
        finally:
            session.close()
    
    
    @app.post("/api/proposals/<id>/approve")
    @safety_guard
    @require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
    def approve_proposal(id: str) -> Any:
        """Approve proposal - FAIL-CLOSED GOVERNANCE."""
        try:
            payload = ApprovalRequest.parse_obj(request.get_json(force=True) or {})
        except ValidationError as exc:
            return jsonify({"error": exc.errors()}), 400
        
        session: Session = get_session()
        try:
            proposal = session.query(Proposal).filter(Proposal.id == id).first()
            if not proposal:
                return jsonify({"error": "Proposal not found"}), 404
            
            if proposal.status == ProposalStatus.APPROVED:
                return jsonify({"error": "Proposal already approved"}), 409
            
            try:
                governance_snapshot = ProposalGovernanceValidator.validate_approval(actor=current_user())
            except GovernanceVetoError as e:
                return jsonify({
                    "error": e.reason,
                    "code": e.code,
                    "governance_snapshot": ProposalGovernanceValidator.capture_creation_snapshot()
                }), 403
            
            user = current_user()
            user_id = user.get("id") if user else None
            
            proposal.status = ProposalStatus.APPROVED
            proposal.approved_by_user_id = user_id
            proposal.approved_at = datetime.utcnow()
            
            intent = ExecutionIntent(
                proposal_id=proposal.id,
                status="PREVIEW_ONLY",
                plan_snapshot=proposal.execution_plan_preview or {},
                governance_snapshot_at_approval=governance_snapshot,
                created_by_user_id=user_id
            )
            session.add(intent)
            session.flush()
            
            audit_event = ProposalAuditEvent(
                proposal_id=proposal.id,
                event_type=ProposalAuditEventType.PROPOSAL_APPROVED,
                actor_user_id=user_id,
                actor_role=user.get("role") if user else None,
                governance_snapshot=governance_snapshot,
                confidence_score_at_decision=proposal.confidence_score,
                data_freshness_state_at_decision=governance_snapshot.get("data_freshness_state"),
                event_metadata={
                    "notes": payload.notes,
                    "size_adjustment": payload.size_adjustment,
                    "execution_intent_id": intent.id
                }
            )
            session.add(audit_event)
            session.commit()
            
            _audit("PROPOSAL_APPROVED", ok=True, details={"proposal_id": id, "intent_id": intent.id})
            
            return jsonify({
                "id": proposal.id,
                "status": "APPROVED",
                "execution_intent_id": intent.id,
                "intent_status": "PREVIEW_ONLY"
            }), 200
        except Exception as e:
            session.rollback()
            logger.error(f"Error approving proposal: {e}")
            return jsonify({"error": str(e)}), 500
        finally:
            session.close()
    
    
    @app.post("/api/proposals/<id>/reject")
    @require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
    def reject_proposal(id: str) -> Any:
        """Reject proposal with mandatory reason."""
        try:
            payload = RejectionRequest.parse_obj(request.get_json(force=True) or {})
        except ValidationError as exc:
            return jsonify({"error": exc.errors()}), 400
        
        session: Session = get_session()
        try:
            proposal = session.query(Proposal).filter(Proposal.id == id).first()
            if not proposal:
                return jsonify({"error": "Proposal not found"}), 404
            
            user = current_user()
            user_id = user.get("id") if user else None
            
            proposal.status = ProposalStatus.REJECTED
            proposal.rejected_by_user_id = user_id
            proposal.rejected_at = datetime.utcnow()
            proposal.rejection_reason = payload.reason
            
            governance_snapshot = ProposalGovernanceValidator.capture_creation_snapshot()
            audit_event = ProposalAuditEvent(
                proposal_id=proposal.id,
                event_type=ProposalAuditEventType.PROPOSAL_REJECTED,
                actor_user_id=user_id,
                actor_role=user.get("role") if user else None,
                governance_snapshot=governance_snapshot,
                confidence_score_at_decision=proposal.confidence_score,
                data_freshness_state_at_decision=governance_snapshot.get("data_freshness_state"),
                event_metadata={"reason": payload.reason, "comment": payload.comment}
            )
            session.add(audit_event)
            session.commit()
            
            _audit("PROPOSAL_REJECTED", ok=True, details={"proposal_id": id, "reason": payload.reason})
            
            return jsonify({"id": proposal.id, "status": "REJECTED"}), 200
        except Exception as e:
            session.rollback()
            logger.error(f"Error rejecting proposal: {e}")
            return jsonify({"error": str(e)}), 500
        finally:
            session.close()
    
    
    @app.post("/api/proposals/<id>/request-changes")
    @require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
    def request_proposal_changes(id: str) -> Any:
        """Request changes to proposal."""
        try:
            payload = RequestChangesRequest.parse_obj(request.get_json(force=True) or {})
        except ValidationError as exc:
            return jsonify({"error": exc.errors()}), 400
        
        session: Session = get_session()
        try:
            proposal = session.query(Proposal).filter(Proposal.id == id).first()
            if not proposal:
                return jsonify({"error": "Proposal not found"}), 404
            
            proposal.status = ProposalStatus.REQUEST_CHANGES
            
            user = current_user()
            user_id = user.get("id") if user else None
            governance_snapshot = ProposalGovernanceValidator.capture_creation_snapshot()
            
            audit_event = ProposalAuditEvent(
                proposal_id=proposal.id,
                event_type=ProposalAuditEventType.PROPOSAL_REQUEST_CHANGES,
                actor_user_id=user_id,
                actor_role=user.get("role") if user else None,
                governance_snapshot=governance_snapshot,
                confidence_score_at_decision=proposal.confidence_score,
                data_freshness_state_at_decision=governance_snapshot.get("data_freshness_state"),
                event_metadata={"requested_changes": payload.requested_changes, "comment": payload.comment}
            )
            session.add(audit_event)
            session.commit()
            
            return jsonify({"id": proposal.id, "status": "REQUEST_CHANGES"}), 200
        except Exception as e:
            session.rollback()
            logger.error(f"Error requesting changes: {e}")
            return jsonify({"error": str(e)}), 500
        finally:
            session.close()
    
    
    @app.get("/api/proposals/<id>/audit")
    @require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
    def get_proposal_audit(id: str) -> Any:
        """Get full audit trail for proposal."""
        session: Session = get_session()
        try:
            proposal = session.query(Proposal).filter(Proposal.id == id).first()
            if not proposal:
                return jsonify({"error": "Proposal not found"}), 404
            
            events = session.query(ProposalAuditEvent).filter(
                ProposalAuditEvent.proposal_id == id
            ).order_by(ProposalAuditEvent.timestamp.asc()).all()
            
            event_list = []
            for e in events:
                event_list.append({
                    "id": e.id,
                    "proposal_id": e.proposal_id,
                    "event_type": e.event_type.value,
                    "actor_user_id": e.actor_user_id,
                    "actor_role": e.actor_role,
                    "timestamp": e.timestamp.isoformat(),
                    "governance_snapshot": e.governance_snapshot,
                    "confidence_score_at_decision": e.confidence_score_at_decision,
                    "data_freshness_state_at_decision": e.data_freshness_state_at_decision.value if e.data_freshness_state_at_decision else None,
                    "event_metadata": e.event_metadata
                })
            
            return jsonify({"proposal_id": id, "events": event_list})
        finally:
            session.close()
    
    
    @app.post("/api/ghost/run")
    @require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
    def run_ghost_test() -> Any:
        """Run deterministic Ghost Test simulation."""
        try:
            payload = GhostTestRequest.parse_obj(request.get_json(force=True) or {})
        except ValidationError as exc:
            return jsonify({"error": exc.errors()}), 400
        
        session: Session = get_session()
        try:
            proposal = session.query(Proposal).filter(Proposal.id == payload.proposal_id).first()
            if not proposal:
                return jsonify({"error": "Proposal not found"}), 404
            
            results = ghost_engine.run_ghost_test(
                asset=proposal.asset,
                action=proposal.action.value,
                thesis_dna=proposal.thesis_dna,
                confidence_score=proposal.confidence_score,
                size_scenarios=payload.size_scenarios
            )
            
            result_list = [r.dict() for r in results]
            
            return jsonify({
                "proposal_id": payload.proposal_id,
                "results": result_list,
                "deterministic": True,
                "timestamp": datetime.utcnow().isoformat()
            })
        finally:
            session.close()
