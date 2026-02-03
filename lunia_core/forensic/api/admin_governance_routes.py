"""Admin Governance Blueprint (PHASE 6 - RBAC + STREAMING AUDIT)

RBAC-hardened governance with segregation of duties + NDJSON audit streaming.
"""
from typing import Optional
from flask import Blueprint, request, jsonify, Response, current_app, stream_with_context
from datetime import datetime

from forensic.risk.store import RiskConfigStore
from forensic.risk.audit import AuditLogger
from forensic.api.auth import Role, validate_rbac, require_ack_for_write, make_error_payload

_store_instance: Optional[RiskConfigStore] = None
_audit_instance: Optional[AuditLogger] = None

def init_governance(config_path: str = "data/risk_config.json", audit_path: str = "data/risk_audit.jsonl"):
    global _store_instance, _audit_instance
    _store_instance = RiskConfigStore(config_path)
    _audit_instance = AuditLogger(audit_path)
    _store_instance.load_or_initialize()

def get_store() -> RiskConfigStore:
    if _store_instance is None:
        raise RuntimeError("Store not initialized")
    return _store_instance

def get_audit() -> AuditLogger:
    if _audit_instance is None:
        raise RuntimeError("Audit not initialized")
    return _audit_instance

admin_bp = Blueprint("admin_bp", __name__)

@admin_bp.post("/governance/mode")
def set_governance_mode() -> Response:
    """Set risk mode (SHADOW/ENFORCE). Roles: ROOT, RISK."""
    request_id = None
    try:
        # L1: RBAC - ROOT or RISK
        rbac = validate_rbac([Role.ROOT, Role.RISK])
        if not rbac.ok:
            current_app.logger.warning(f"[RBAC_DENY] {rbac.error_code} role={rbac.role}")
            return jsonify(make_error_payload(rbac.error_code, rbac.message)), rbac.status_code
        
        # L2: ACK required for write
        ack = require_ack_for_write()
        if not ack.ok:
            current_app.logger.warning(f"[ACK_DENY] {ack.error_code}")
            return jsonify(make_error_payload(ack.error_code, ack.message)), ack.status_code
        
        body = request.get_json() or {}
        mode, reason, request_id = body.get("mode"), body.get("reason", ""), body.get("request_id", "")
        
        if mode not in ["SHADOW", "ENFORCE"]:
            return jsonify(make_error_payload("INVALID_REQUEST", "mode must be SHADOW or ENFORCE", request_id)), 400
        if not reason or len(reason) < 10 or len(reason) > 2000:
            return jsonify(make_error_payload("INVALID_REQUEST", "reason 10-2000 chars", request_id)), 400
        if not request_id or len(request_id) < 8 or len(request_id) > 128:
            return jsonify(make_error_payload("INVALID_REQUEST", "request_id 8-128 chars", request_id)), 400
        
        current_app.logger.info(f"[ADMIN_ATTEMPT] SET_GOVERNANCE_MODE request_id={request_id} mode={mode} role={rbac.role.value}")
        
        store = get_store()
        audit = get_audit()
        
        # ATOMIC TRANSACTION
        with store.locked_transaction():
            # Idempotency check
            existing = audit.find_by_request_id(request_id)
            if existing:
                current_app.logger.info(f"[ADMIN_SUCCESS] idempotent_replay request_id={request_id}")
                return jsonify({"status": "ok", "action": "SET_GOVERNANCE_MODE", "request_id": request_id, "previous": existing["previous_state"], "current": existing["new_state"], "audit": {"id": existing["audit_id"], "timestamp": existing["timestamp"]}, "_note": "idempotent_reply"}), 200
            
            # Backup
            backup = store.snapshot_backup_nolock()
            
            try:
                # Update config
                previous = store._load_or_initialize_nolock()
                new = store.update_mode(mode, rbac.role.value, reason, request_id)
                
                # Append audit (with internal idempotency check)
                audit_id = audit.log_change("SET_GOVERNANCE_MODE", request_id, rbac.role.value, reason, previous, new, True, None)
                
                current_app.logger.info(f"[ADMIN_APPLY] SET_GOVERNANCE_MODE mode={mode} version={new['version']}")
                current_app.logger.info(f"[ADMIN_SUCCESS] request_id={request_id} audit_id={audit_id}")
                
                return jsonify({"status": "ok", "action": "SET_GOVERNANCE_MODE", "request_id": request_id, "previous": {"mode": previous["mode"], "version": previous["version"]}, "current": {"mode": new["mode"], "version": new["version"]}, "audit": {"id": audit_id, "timestamp": new["updated_at"]}}), 200
                
            except Exception as e:
                # Rollback config if error
                if backup:
                    store.rollback_nolock(backup)
                    current_app.logger.error(f"[ADMIN_ERROR] request_id={request_id} rolled_back")
                raise RuntimeError(f"[AUDIT_WRITE_ERROR] {e}")
        
    except RuntimeError as e:
        error_code = "INTEGRITY_CHECK_FAILED" if "INTEGRITY" in str(e) else ("AUDIT_WRITE_ERROR" if "AUDIT" in str(e) else "GOVERNANCE_PERSISTENCE_ERROR")
        current_app.logger.error(f"[ADMIN_ERROR] request_id={request_id} error={error_code}")
        return jsonify(make_error_payload(error_code, str(e), request_id)), 503

@admin_bp.post("/governance/halt")
def set_global_halt() -> Response:
    """Set global halt. Roles: ROOT ONLY."""
    request_id = None
    try:
        # L1: RBAC - ROOT ONLY
        rbac = validate_rbac([Role.ROOT])
        if not rbac.ok:
            current_app.logger.warning(f"[RBAC_DENY] {rbac.error_code} role={rbac.role}")
            return jsonify(make_error_payload(rbac.error_code, rbac.message)), rbac.status_code
        
        # L2: ACK required for write
        ack = require_ack_for_write()
        if not ack.ok:
            current_app.logger.warning(f"[ACK_DENY] {ack.error_code}")
            return jsonify(make_error_payload(ack.error_code, ack.message)), ack.status_code
        
        body = request.get_json() or {}
        halt, reason, request_id = body.get("halt"), body.get("reason", ""), body.get("request_id", "")
        
        if not isinstance(halt, bool):
            return jsonify(make_error_payload("INVALID_REQUEST", "halt must be boolean", request_id)), 400
        if not reason or len(reason) < 10 or len(reason) > 2000:
            return jsonify(make_error_payload("INVALID_REQUEST", "reason 10-2000 chars", request_id)), 400
        if not request_id or len(request_id) < 8 or len(request_id) > 128:
            return jsonify(make_error_payload("INVALID_REQUEST", "request_id 8-128 chars", request_id)), 400
        
        current_app.logger.info(f"[ADMIN_ATTEMPT] SET_GLOBAL_HALT request_id={request_id} halt={halt} role={rbac.role.value}")
        
        store = get_store()
        audit = get_audit()
        
        # ATOMIC TRANSACTION
        with store.locked_transaction():
            existing = audit.find_by_request_id(request_id)
            if existing:
                current_app.logger.info(f"[ADMIN_SUCCESS] idempotent_replay request_id={request_id}")
                return jsonify({"status": "ok", "action": "SET_GLOBAL_HALT", "request_id": request_id, "previous": existing["previous_state"], "current": existing["new_state"], "audit": {"id": existing["audit_id"], "timestamp": existing["timestamp"]}, "_note": "idempotent_reply"}), 200
            
            backup = store.snapshot_backup_nolock()
            
            try:
                previous = store._load_or_initialize_nolock()
                new = store.update_halt(halt, rbac.role.value, reason, request_id)
                audit_id = audit.log_change("SET_GLOBAL_HALT", request_id, rbac.role.value, reason, previous, new, True, None)
                
                current_app.logger.info(f"[ADMIN_APPLY] SET_GLOBAL_HALT halt={halt} version={new['version']}")
                current_app.logger.info(f"[ADMIN_SUCCESS] request_id={request_id} audit_id={audit_id}")
                
                return jsonify({"status": "ok", "action": "SET_GLOBAL_HALT", "request_id": request_id, "previous": {"is_halted": previous["is_halted"], "version": previous["version"]}, "current": {"is_halted": new["is_halted"], "version": new["version"]}, "audit": {"id": audit_id, "timestamp": new["updated_at"]}}), 200
                
            except Exception as e:
                if backup:
                    store.rollback_nolock(backup)
                    current_app.logger.error(f"[ADMIN_ERROR] request_id={request_id} rolled_back")
                raise RuntimeError(f"[AUDIT_WRITE_ERROR] {e}")
        
    except RuntimeError as e:
        error_code = "INTEGRITY_CHECK_FAILED" if "INTEGRITY" in str(e) else ("AUDIT_WRITE_ERROR" if "AUDIT" in str(e) else "GOVERNANCE_PERSISTENCE_ERROR")
        current_app.logger.error(f"[ADMIN_ERROR] request_id={request_id} error={error_code}")
        return jsonify(make_error_payload(error_code, str(e), request_id)), 503

@admin_bp.get("/audit")
def get_audit_stream() -> Response:
    """Stream audit log as NDJSON. Roles: ROOT, AUDITOR."""
    try:
        # L1: RBAC - ROOT or AUDITOR
        rbac = validate_rbac([Role.ROOT, Role.AUDITOR])
        if not rbac.ok:
            current_app.logger.warning(f"[RBAC_DENY] {rbac.error_code} role={rbac.role}")
            return jsonify(make_error_payload(rbac.error_code, rbac.message)), rbac.status_code
        
        # Parse query params
        try:
            limit = int(request.args.get("limit", "100"))
        except ValueError:
            return jsonify(make_error_payload("INVALID_REQUEST", "limit must be integer")), 400
        
        if limit > 1000:
            return jsonify(make_error_payload("LIMIT_EXCEEDED", "limit must be <= 1000")), 400
        if limit < 1:
            return jsonify(make_error_payload("INVALID_REQUEST", "limit must be >= 1")), 400
        
        actor = request.args.get("actor")
        action = request.args.get("action")
        request_id_filter = request.args.get("request_id")
        
        current_app.logger.info(f"[AUDIT_STREAM] limit={limit} actor={actor} action={action} request_id={request_id_filter} role={rbac.role.value}")
        
        audit = get_audit()
        
        # Stream NDJSON
        def generate():
            try:
                for line in audit.stream_records(limit=limit, actor=actor, action=action, request_id=request_id_filter):
                    yield line
            except Exception as e:
                # Catastrophic error - yield final error line
                current_app.logger.error(f"[AUDIT_STREAM_ERROR] {e}")
                import json
                yield json.dumps({
                    "type": "error",
                    "error": "STREAM_FATAL_ERROR",
                    "message": str(e)[:200],
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }) + "\n"
        
        return Response(stream_with_context(generate()), mimetype="application/x-ndjson")
        
    except Exception as e:
        current_app.logger.error(f"[AUDIT_ERROR] {e}")
        return jsonify(make_error_payload("AUDIT_READ_ERROR", str(e))), 500
