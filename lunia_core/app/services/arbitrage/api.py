"""REST API for arbitrage controls."""
from __future__ import annotations

import os
from typing import Any, Dict

from flask import Blueprint, jsonify, request

from .worker import (
    auto_tick,
    execute_by_id,
    get_execution,
    get_filters,
    get_state,
    scan_now,
    toggle_auto_mode,
    update_filters,
)

bp = Blueprint("arbitrage", __name__, url_prefix="/arbitrage")
OPS_TOKEN = os.getenv("OPS_API_TOKEN")


def _ensure_admin() -> None:
    if not OPS_TOKEN:
        return
    header = request.headers.get("X-OPS-TOKEN")
    if header != OPS_TOKEN:
        raise PermissionError("invalid token")


def _serialize_filters(filters) -> Dict[str, Any]:
    return {
        "min_net_roi_pct": filters.min_net_roi_pct,
        "max_net_roi_pct": filters.max_net_roi_pct,
        "min_net_usd": filters.min_net_usd,
        "top_k": filters.top_k,
        "sort_key": filters.sort_key,
        "sort_dir": filters.sort_dir,
    }


@bp.post("/scan")
def post_scan() -> Any:
    _ensure_admin()
    data = scan_now()
    return jsonify({"opportunities": data})


@bp.get("/top")
def get_top() -> Any:
    limit = request.args.get("limit", type=int)
    state = get_state()
    opportunities = state.last_opportunities
    if limit is not None:
        opportunities = opportunities[: max(1, limit)]
    return jsonify({"opportunities": opportunities, "filters": _serialize_filters(get_filters())})


@bp.post("/exec")
def post_exec() -> Any:
    _ensure_admin()
    payload = request.get_json(force=True) or {}
    proposal_id = payload.get("arb_id")
    mode = payload.get("mode")
    transfer = payload.get("transfer", "auto")
    pin = payload.get("pin")
    double_confirm = bool(payload.get("double_confirm", False))
    if not proposal_id:
        raise ValueError("arb_id is required")
    result = execute_by_id(
        proposal_id,
        mode=mode,
        transfer=transfer,
        pin=pin,
        double_confirm=double_confirm,
    )
    return jsonify(result)


@bp.post("/auto_on")
def post_auto_on() -> Any:
    _ensure_admin()
    state = toggle_auto_mode(True)
    return jsonify(state)


@bp.post("/auto_off")
def post_auto_off() -> Any:
    _ensure_admin()
    state = toggle_auto_mode(False)
    return jsonify(state)


@bp.get("/filters")
def get_filters_endpoint() -> Any:
    filters = get_filters()
    return jsonify(_serialize_filters(filters))


@bp.post("/filters")
def post_filters_endpoint() -> Any:
    _ensure_admin()
    payload = request.get_json(force=True) or {}
    update_filters(payload)
    filters = get_filters()
    return jsonify(_serialize_filters(filters))


@bp.get("/status")
def get_status() -> Any:
    runtime = get_state()
    data = runtime.snapshot()
    data["last_opportunities"] = runtime.last_opportunities
    return jsonify(data)


@bp.get("/status/<exec_id>")
def get_exec_status(exec_id: str) -> Any:
    execution = get_execution(exec_id)
    if not execution:
        return jsonify({"error": "not_found"}), 404
    return jsonify(execution)


@bp.post("/auto/tick")
def post_auto_tick() -> Any:
    _ensure_admin()
    reason = auto_tick()
    return jsonify({"result": reason})


@bp.errorhandler(PermissionError)
def _handle_permission(error: PermissionError):
    return jsonify({"error": str(error)}), 403


__all__ = ["bp"]
