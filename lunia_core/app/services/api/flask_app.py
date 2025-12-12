"""Flask API exposing Lunia core functionality."""
from __future__ import annotations

import logging
import os
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from app.compat.dotenv import load_dotenv
from flask import Flask, Response, g, jsonify, request
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ...boot import CORES
from ...core.ai.agent import Agent
from ...core.ai.supervisor import Supervisor
from ...core.ai.strategies import REGISTRY, StrategySignal
from ...core.exchange.binance_futures import BinanceFutures
from ...core.exchange.binance_spot import BinanceSpot
from ...core.capital.allocator import CapitalAllocator
from ...core.metrics import (
    api_latency_ms,
    ensure_metrics_server,
    orders_rejected_total,
    orders_total,
    scrape_metrics,
)
from ...core.risk.manager import RiskManager
from ...core.state import get_state as get_runtime_state, set_state
from ..auth.audit import record_audit
from ..auth.database import Base, engine, get_session, init_db
from ..auth.models import AuditEvent, FeatureFlag, Limit, User
from ..auth.rbac import current_user, require_auth, require_role
from ..auth.security import create_access_token, decode_token, get_user, get_user_by_email, verify_password
from ..auth.users import create_user, ensure_seed_admin, list_users, touch_last_login, update_user
from ..ai_research import run_research_now
from ..arbitrage import bp as arbitrage_bp
from ..arbitrage.worker import get_state as get_arbitrage_state
from ..api.schemas import (
    ActivityItem,
    ActivityResponse,
    ArbitrageOpportunities,
    AuditEventSchema,
    BalancesResponse,
    CapitalRequest,
    FeatureFlagSchema,
    FuturesTradeRequest,
    LimitSchema,
    LogEntry,
    LoginRequest,
    LoginResponse,
    OpsState,
    OpsStateUpdate,
    PortfolioAggregate,
    PortfolioPosition,
    PortfolioSnapshot,
    ReserveUpdateRequest,
    ResearchRequest,
    ResearchResponse,
    SignalPayload,
    SignalsEnvelope,
    SignalsFeed,
    SignalFeedItem,
    SpotRiskUpdate,
    StrategyWeightsRequest,
    TradeRequest,
    UserOut,
)

load_dotenv()

LOG_DIR = Path(__file__).resolve().parents[4] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
API_LOG_PATH = LOG_DIR / "api.log"
OPS_TOKEN = os.getenv("OPS_API_TOKEN")
AUTH_REQUIRED_FOR_TELEMETRY = os.getenv("AUTH_REQUIRED_FOR_TELEMETRY", "1").lower() == "1"
DEFAULT_FLAGS = {
    "FEATURE_TELEGRAM": os.getenv("FEATURE_TELEGRAM", "0"),
    "FEATURE_MANUAL_MODE": os.getenv("FEATURE_MANUAL_MODE", "1"),
    "FEATURE_ARBITRAGE": os.getenv("FEATURE_ARBITRAGE", "1"),
    "FEATURE_FUTURES": os.getenv("FEATURE_FUTURES", "0"),
}
DEFAULT_LIMITS: list[dict[str, Any]] = []

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.FileHandler(API_LOG_PATH, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

START_TIME = time.time()
ACTIVITY_LOG: deque[ActivityItem] = deque(maxlen=100)

init_db(lambda: Base.metadata.create_all(bind=engine))
with get_session() as _session:
    ensure_seed_admin(
        _session,
        email=os.getenv("ADMIN_EMAIL"),
        password=os.getenv("ADMIN_PASSWORD"),
    )
    for key, value in DEFAULT_FLAGS.items():
        existing = _session.query(FeatureFlag).filter(FeatureFlag.key == key).one_or_none()
        if not existing:
            _session.add(FeatureFlag(key=key, value=str(value), updated_by=None))
    _session.commit()


def _measure_latency(func):
    def wrapper(*args: Any, **kwargs: Any):
        start = time.time()
        try:
            return func(*args, **kwargs)
        finally:
            duration_ms = (time.time() - start) * 1000
            api_latency_ms.observe(duration_ms)

    wrapper.__name__ = func.__name__
    return wrapper


def _log_activity(action: str, *, ok: bool = True, details: str | None = None) -> None:
    entry = ActivityItem(
        ts=datetime.utcnow().isoformat(),
        actor="api",
        action=action,
        ok=ok,
        details=details,
    )
    ACTIVITY_LOG.appendleft(entry)


def _audit(action: str, *, ok: bool = True, target: str | None = None, details: Dict[str, Any] | None = None) -> None:
    db: Optional[Session] = getattr(g, "db", None)
    if db:
        record_audit(
            db,
            action=action,
            result="OK" if ok else "FAIL",
            target=target,
            metadata=details,
        )
    _log_activity(action, ok=ok, details=str(details) if details else target)


def create_agent() -> Agent:
    use_testnet = os.getenv("BINANCE_USE_TESTNET", "true").lower() == "true"
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    client = BinanceSpot(
        api_key=api_key,
        api_secret=api_secret,
        use_testnet=use_testnet,
        mock=not use_testnet,
    )
    risk = RiskManager()
    supervisor = Supervisor(client=client)
    return Agent(client=client, risk=risk, supervisor=supervisor)


agent = create_agent()
supervisor = agent.supervisor
futures_risk = RiskManager()


def create_futures_client() -> BinanceFutures:
    use_testnet = os.getenv("BINANCE_FUTURES_TESTNET", "true").lower() == "true"
    api_key = os.getenv("BINANCE_FUTURES_API_KEY")
    api_secret = os.getenv("BINANCE_FUTURES_API_SECRET")
    return BinanceFutures(
        api_key=api_key,
        api_secret=api_secret,
        use_testnet=use_testnet,
        mock=not use_testnet,
    )


futures_client = create_futures_client()
app = Flask(__name__)
ensure_metrics_server(9100)
app.register_blueprint(arbitrage_bp)

ALLOWED_ORIGINS = os.getenv("CORS_ALLOW_ORIGINS", "*")
ALLOWED_HEADERS = os.getenv(
    "CORS_ALLOW_HEADERS",
    "Content-Type,Authorization,X-Admin-Token,X-OPS-TOKEN",
)


@app.after_request
def _add_cors_headers(response: Response) -> Response:
    response.headers["Access-Control-Allow-Origin"] = ALLOWED_ORIGINS
    response.headers["Access-Control-Allow-Headers"] = ALLOWED_HEADERS
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    response.headers["Access-Control-Expose-Headers"] = "Content-Type"
    return response


@app.before_request
def _inject_db_and_user() -> None:
    g.db = get_session()
    g.current_user = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        payload = decode_token(token)
        if payload and payload.get("sub"):
            user = get_user(g.db, int(payload["sub"]))
            if user:
                g.current_user = user


@app.teardown_request
def _teardown_db(exc: Optional[BaseException]) -> None:
    db: Optional[Session] = getattr(g, "db", None)
    if db:
        db.close()


@app.post("/auth/login")
@_measure_latency
def auth_login() -> Any:
    try:
        payload = LoginRequest.parse_obj(request.get_json(force=True) or {})
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 400
    session: Session = g.db
    user = get_user_by_email(session, payload.email.lower())
    if not user or not verify_password(payload.password, user.password_hash):
        _audit("auth_login", ok=False, target=payload.email)
        return jsonify({"error": "invalid_credentials"}), 401

    token, expires_at = create_access_token(user)
    touch_last_login(session, user)
    _audit("auth_login", ok=True, target=payload.email)
    response = LoginResponse(
        access_token=token,
        role=user.role,
        user_id=user.id,
        expires_at=expires_at.isoformat(),
    )
    return jsonify(response.dict())


@app.get("/auth/me")
@_measure_latency
@require_auth()
def auth_me() -> Any:
    user: Optional[User] = current_user()
    if not user:
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(_user_payload(user))


@app.post("/auth/logout")
@_measure_latency
@require_auth(optional=True)
def auth_logout() -> Any:
    user: Optional[User] = current_user()
    if user:
        _audit("auth_logout", target=user.email)
    return jsonify({"ok": True})


def _allocator_from_state(state: Dict[str, Any]) -> CapitalAllocator:
    spot_cfg = state.get("spot", {})
    return CapitalAllocator(
        max_trade_pct=float(spot_cfg.get("max_trade_pct", 0.20)),
        risk_per_trade_pct=float(spot_cfg.get("risk_per_trade_pct", 0.005)),
        max_symbol_exposure_pct=float(spot_cfg.get("max_symbol_exposure_pct", 0.35)) * 100,
        max_positions=int(spot_cfg.get("max_positions", 5)),
    )


def _capital_snapshot() -> Dict[str, Any]:
    state = get_runtime_state()
    allocator = _allocator_from_state(state)
    reserves = state.get("reserves", {})
    ops_state = state.get("ops", {})
    capital_cfg = ops_state.get("capital", {}) if isinstance(ops_state, dict) else {}
    cap_pct = float(capital_cfg.get("cap_pct", 0.25))
    equity_guess = float(state.get("portfolio_equity", agent.default_equity_usd))
    equity = agent.portfolio.get_equity_usd({"USDT": equity_guess})
    allocation = allocator.compute_budgets(
        equity=equity,
        cap_pct=cap_pct,
        reserves=reserves,
        weights=state.get("spot", {}).get("weights", {}),
    )
    return {
        "state": state,
        "allocator": allocator,
        "equity": equity,
        "allocation": allocation,
        "cap_pct": cap_pct,
    }


def _activity_components(runtime: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    arb_state = runtime.get("arb", {}) if isinstance(runtime, dict) else {}
    arb_runtime = get_arbitrage_state()
    return {
        "scheduler": {
            "status": "on" if runtime.get("sched_on", True) else "off",
            "last_tick": runtime.get("sched_last_run"),
            "notes": None,
        },
        "arbitrage": {
            "status": "on" if arb_state.get("auto_mode", False) else "off",
            "last_tick": getattr(arb_runtime, "last_scan_ts", None) or 0.0,
            "notes": getattr(arb_runtime, "last_decision", ""),
        },
        "spot": {
            "status": "on" if runtime.get("spot", {}).get("enabled", True) else "off",
            "last_tick": None,
            "notes": None,
        },
        "futures": {
            "status": "on" if runtime.get("trading_on", True) else "off",
            "last_tick": None,
            "notes": None,
        },
    }


def _ensure_admin_request() -> bool:
    user = current_user()
    if user and user.role in {"ADMIN", "TRADER"}:
        return True
    if OPS_TOKEN is None:
        return False
    header = request.headers.get("X-Admin-Token")
    return header == OPS_TOKEN


def _telemetry_guard():
    if not AUTH_REQUIRED_FOR_TELEMETRY:
        return None
    if OPS_TOKEN and request.headers.get("X-Admin-Token") == OPS_TOKEN:
        return None
    if current_user():
        return None
    return jsonify({"error": "unauthorized"}), 401


def _feature_flags(session: Session) -> Dict[str, Any]:
    flags = {**DEFAULT_FLAGS}
    for flag in session.query(FeatureFlag).all():
        flags[flag.key] = flag.value
    return flags


def _limits(session: Session) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for item in session.query(Limit).all():
        results.append(
            {
                "scope": item.scope,
                "subject": item.subject,
                "key": item.key,
                "value": item.value,
                "updated_at": item.updated_at.isoformat(),
                "updated_by": item.updated_by,
            }
        )
    return results


def _user_payload(user: User) -> Dict[str, Any]:
    return UserOut(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at.isoformat(),
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
    ).dict()


@app.get("/health")
@_measure_latency
def health() -> Any:
    logger.info("/health requested")
    return jsonify({"status": "ok"})


@app.get("/metrics")
def metrics() -> Any:
    guard = _telemetry_guard()
    if guard:
        return guard
    return Response(scrape_metrics(), mimetype="text/plain; version=0.0.4")


@app.get("/cores")
@_measure_latency
def cores() -> Any:
    guard = _telemetry_guard()
    if guard:
        return guard
    logger.info("/cores requested")
    return jsonify(CORES)


@app.get("/status")
@_measure_latency
def status() -> Any:
    guard = _telemetry_guard()
    if guard:
        return guard
    logger.info("/status requested")
    uptime = time.time() - START_TIME
    active = {name: cfg for name, cfg in CORES.items() if cfg.get("enabled")}
    payload = {
        "version": "0.1.0",
        "uptime": uptime,
        "active_cores": active,
        "timestamp": datetime.utcnow().isoformat(),
    }
    return jsonify(payload)


@app.get("/admin/users")
@_measure_latency
@require_role("ADMIN", ops_token=OPS_TOKEN)
def admin_users() -> Any:
    session: Session = g.db
    items = [_user_payload(user) for user in list_users(session)]
    return jsonify({"items": items})


@app.post("/admin/users")
@_measure_latency
@require_role("ADMIN", ops_token=OPS_TOKEN)
def admin_create_user() -> Any:
    body = request.get_json(force=True) or {}
    email = str(body.get("email", "")).strip().lower()
    password = body.get("password")
    role = str(body.get("role", "USER")).upper()
    if not email or not password:
        return jsonify({"error": "email and password required"}), 400
    session: Session = g.db
    existing = get_user_by_email(session, email)
    if existing:
        return jsonify({"error": "user_exists"}), 409
    user = create_user(session, email=email, password=password, role=role)
    _audit("admin_create_user", target=email)
    return jsonify(_user_payload(user)), 201


@app.put("/admin/users/<int:user_id>")
@_measure_latency
@require_role("ADMIN", ops_token=OPS_TOKEN)
def admin_update_user(user_id: int) -> Any:
    body = request.get_json(force=True) or {}
    session: Session = g.db
    user = get_user(session, user_id)
    if not user:
        return jsonify({"error": "not_found"}), 404
    role = body.get("role")
    is_active = body.get("is_active")
    updated = update_user(session, user, role=role, is_active=is_active)
    _audit("admin_update_user", target=str(user_id), details={"role": role, "is_active": is_active})
    return jsonify(_user_payload(updated))


@app.get("/admin/flags")
@_measure_latency
@require_role("ADMIN", ops_token=OPS_TOKEN)
def admin_flags() -> Any:
    session: Session = g.db
    flags = [
        FeatureFlagSchema(
            key=flag.key,
            value=flag.value,
            updated_at=flag.updated_at.isoformat(),
            updated_by=flag.updated_by,
        ).dict()
        for flag in session.query(FeatureFlag).order_by(FeatureFlag.key.asc()).all()
    ]
    return jsonify({"items": flags})


@app.put("/admin/flags/<key>")
@_measure_latency
@require_role("ADMIN", ops_token=OPS_TOKEN)
def admin_update_flag(key: str) -> Any:
    session: Session = g.db
    body = request.get_json(force=True) or {}
    value = body.get("value")
    flag = session.query(FeatureFlag).filter(FeatureFlag.key == key).one_or_none()
    actor = current_user()
    if flag:
        flag.value = str(value)
        flag.updated_by = actor.id if actor else None
    else:
        flag = FeatureFlag(key=key, value=str(value), updated_by=actor.id if actor else None)
        session.add(flag)
    session.commit()
    session.refresh(flag)
    _audit("admin_update_flag", target=key, details={"value": value})
    return jsonify(
        FeatureFlagSchema(
            key=flag.key,
            value=flag.value,
            updated_at=flag.updated_at.isoformat(),
            updated_by=flag.updated_by,
        ).dict()
    )


@app.get("/admin/limits")
@_measure_latency
@require_role("ADMIN", ops_token=OPS_TOKEN)
def admin_limits() -> Any:
    session: Session = g.db
    items = [
        LimitSchema(
            scope=item.scope,
            subject=item.subject,
            key=item.key,
            value=item.value,
            updated_at=item.updated_at.isoformat(),
            updated_by=item.updated_by,
        ).dict()
        for item in session.query(Limit).order_by(Limit.updated_at.desc()).all()
    ]
    return jsonify({"items": items})


@app.put("/admin/limits")
@_measure_latency
@require_role("ADMIN", ops_token=OPS_TOKEN)
def admin_upsert_limit() -> Any:
    session: Session = g.db
    body = request.get_json(force=True) or {}
    scope = str(body.get("scope", "global"))
    subject = body.get("subject")
    key = str(body.get("key", "")).strip()
    value = body.get("value")
    if not key:
        return jsonify({"error": "key required"}), 400
    record = (
        session.query(Limit)
        .filter(Limit.scope == scope, Limit.subject == subject, Limit.key == key)
        .one_or_none()
    )
    actor = current_user()
    if record:
        record.value = str(value)
        record.updated_by = actor.id if actor else None
    else:
        record = Limit(
            scope=scope,
            subject=subject,
            key=key,
            value=str(value),
            updated_by=actor.id if actor else None,
        )
        session.add(record)
    session.commit()
    session.refresh(record)
    _audit("admin_update_limit", target=key, details={"scope": scope, "subject": subject, "value": value})
    return jsonify(
        LimitSchema(
            scope=record.scope,
            subject=record.subject,
            key=record.key,
            value=record.value,
            updated_at=record.updated_at.isoformat(),
            updated_by=record.updated_by,
        ).dict()
    )


@app.get("/admin/audit")
@_measure_latency
@require_role("ADMIN", ops_token=OPS_TOKEN)
def admin_audit() -> Any:
    session: Session = g.db
    args = request.args
    limit = min(int(args.get("limit", 100)), 500)
    query = session.query(AuditEvent).order_by(AuditEvent.ts.desc())
    if args.get("actor"):
        query = query.filter(AuditEvent.actor_role == args.get("actor"))
    if args.get("action"):
        query = query.filter(AuditEvent.action == args.get("action"))
    if args.get("result"):
        query = query.filter(AuditEvent.result == args.get("result"))
    events = query.limit(limit).all()
    payload = [
        AuditEventSchema(
            id=event.id,
            ts=event.ts.isoformat(),
            actor_user_id=event.actor_user_id,
            actor_role=event.actor_role,
            action=event.action,
            target=event.target,
            result=event.result,
            ip=event.ip,
            user_agent=event.user_agent,
            metadata=event.metadata,
        ).dict()
        for event in events
    ]
    return jsonify({"items": payload})


@app.get("/ops/activity")
@_measure_latency
def ops_activity() -> Any:
    guard = _telemetry_guard()
    if guard:
        return guard
    runtime = get_runtime_state()
    session: Session = g.db
    audit_items: List[ActivityItem] = []
    try:
        events = session.query(AuditEvent).order_by(AuditEvent.ts.desc()).limit(20).all()
        for event in events:
            audit_items.append(
                ActivityItem(
                    ts=event.ts.isoformat(),
                    actor=event.actor_role or "unknown",
                    action=event.action,
                    ok=event.result == "OK",
                    details=event.target,
                )
            )
    except Exception:
        audit_items = []
    payload = ActivityResponse(
        components=_activity_components(runtime),
        last_actions=(audit_items + list(ACTIVITY_LOG))[:50],
        warnings=[],
    )
    return jsonify(payload.dict())


@app.get("/ops/state")
@_measure_latency
def ops_state() -> Any:
    guard = _telemetry_guard()
    if guard:
        return guard
    logger.info("/ops/state requested")
    state = OpsState.parse_obj(get_runtime_state())
    return jsonify(state.dict())


@app.post("/ops/state")
@_measure_latency
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
def ops_state_update() -> Any:
    payload = OpsStateUpdate.parse_obj(request.get_json(force=True) or {})
    filtered = {k: v for k, v in payload.dict().items() if v is not None}
    state = set_state(filtered)
    logger.info("Ops state updated: %s", filtered)
    _audit("ops_state_update", details=filtered)
    return jsonify(OpsState.parse_obj(state).dict())


def _ops_toggle(key: str, value: bool) -> Any:
    if not _ensure_admin_request():
        return jsonify({"error": "forbidden"}), 403
    state = set_state({key: value})
    _audit(f"{key}={value}")
    return jsonify(OpsState.parse_obj(state).dict())


@app.post("/ops/auto_on")
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
def ops_auto_on() -> Any:
    return _ops_toggle("auto_mode", True)


@app.post("/ops/auto_off")
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
def ops_auto_off() -> Any:
    return _ops_toggle("auto_mode", False)


@app.post("/ops/stop_all")
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
def ops_stop_all() -> Any:
    return _ops_toggle("global_stop", True)


@app.post("/ops/start_all")
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
def ops_start_all() -> Any:
    return _ops_toggle("global_stop", False)


@app.get("/ops/equity")
@_measure_latency
def ops_equity() -> Any:
    guard = _telemetry_guard()
    if guard:
        return guard
    snapshot = _capital_snapshot()
    payload = {
        "equity_total_usd": snapshot["equity"],
        "tradable_equity_usd": snapshot["allocation"].tradable_equity,
        "cap_pct": snapshot["cap_pct"],
    }
    return jsonify(payload)


@app.get("/ops/capital")
@_measure_latency
def ops_capital() -> Any:
    guard = _telemetry_guard()
    if guard:
        return guard
    snapshot = _capital_snapshot()
    payload = {
        "cap_pct": snapshot["cap_pct"],
        "equity_total_usd": snapshot["equity"],
        "tradable_equity_usd": snapshot["allocation"].tradable_equity,
        "per_strategy_budgets": snapshot["allocation"].per_strategy,
        "reserves": snapshot["state"].get("reserves", {}),
    }
    return jsonify(payload)


@app.post("/ops/capital")
@_measure_latency
@require_role("ADMIN", ops_token=OPS_TOKEN)
def ops_capital_update() -> Any:
    payload = CapitalRequest.parse_obj(request.get_json(force=True) or {})
    state = set_state({"ops": {"capital": {"cap_pct": payload.cap_pct}}})
    snapshot = _capital_snapshot()
    response = {
        "state": OpsState.parse_obj(state).dict(),
        "cap_pct": snapshot["cap_pct"],
        "tradable_equity_usd": snapshot["allocation"].tradable_equity,
    }
    _audit("ops_capital_update", details=payload.dict())
    return jsonify(response)


@app.get("/spot/strategies")
@_measure_latency
def spot_strategies() -> Any:
    state = get_runtime_state()
    spot_cfg = state.get("spot", {})
    payload = {
        "enabled": bool(spot_cfg.get("enabled", True)),
        "weights": spot_cfg.get("weights", {}),
    }
    return jsonify(payload)


@app.post("/spot/strategies")
@_measure_latency
def spot_strategies_update() -> Any:
    if not _ensure_admin_request():
        return jsonify({"error": "forbidden"}), 403
    payload = StrategyWeightsRequest.parse_obj(request.get_json(force=True) or {})
    update: Dict[str, Any] = {"spot": {"weights": payload.weights}}
    if payload.enabled is not None:
        update["spot"]["enabled"] = payload.enabled
    state = set_state(update)
    _log_activity("spot_strategies_update", details=str(update))
    return jsonify(OpsState.parse_obj(state).dict())


@app.get("/spot/alloc")
@_measure_latency
def spot_alloc() -> Any:
    snapshot = _capital_snapshot()
    return jsonify(
        {
            "tradable_equity_usd": snapshot["allocation"].tradable_equity,
            "per_strategy_budgets": snapshot["allocation"].per_strategy,
            "reserves": snapshot["state"].get("reserves", {}),
        }
    )


@app.post("/spot/alloc")
@_measure_latency
@require_role("ADMIN", ops_token=OPS_TOKEN)
def spot_alloc_update() -> Any:
    payload = ReserveUpdateRequest.parse_obj(request.get_json(force=True) or {})
    update: Dict[str, Any] = {"reserves": {}}
    if payload.portfolio is not None:
        update["reserves"]["portfolio"] = payload.portfolio
    if payload.arbitrage is not None:
        update["reserves"]["arbitrage"] = payload.arbitrage
    state = set_state(update)
    _audit("spot_alloc_update", details=update)
    return jsonify(OpsState.parse_obj(state).dict())


@app.get("/spot/risk")
@_measure_latency
def spot_risk() -> Any:
    guard = _telemetry_guard()
    if guard:
        return guard
    state = get_runtime_state()
    spot_cfg = state.get("spot", {})
    payload = {
        "max_positions": spot_cfg.get("max_positions"),
        "max_trade_pct": spot_cfg.get("max_trade_pct"),
        "risk_per_trade_pct": spot_cfg.get("risk_per_trade_pct"),
        "max_symbol_exposure_pct": spot_cfg.get("max_symbol_exposure_pct"),
        "tp_pct_default": spot_cfg.get("tp_pct_default"),
        "sl_pct_default": spot_cfg.get("sl_pct_default"),
    }
    return jsonify(payload)


@app.post("/spot/risk")
@_measure_latency
@require_role("ADMIN", ops_token=OPS_TOKEN)
def spot_risk_update() -> Any:
    payload = SpotRiskUpdate.parse_obj(request.get_json(force=True) or {})
    update = {"spot": {k: v for k, v in payload.dict(exclude_none=True).items()}}
    state = set_state(update)
    _audit("spot_risk_update", details=update)
    return jsonify(OpsState.parse_obj(state).dict())


@app.post("/spot/backtest")
@_measure_latency
@require_role("ADMIN", ops_token=OPS_TOKEN)
def spot_backtest() -> Any:
    body = request.get_json(force=True) or {}
    strategy = str(body.get("strategy", "scalping_breakout"))
    symbol = str(body.get("symbol", "BTCUSDT"))
    days = int(body.get("days", 7))
    func = REGISTRY.get(strategy)
    if func is None:
        return jsonify({"error": "unknown strategy"}), 400
    state = get_runtime_state()
    prices = list(supervisor.price_history.get(symbol, deque([100.0], maxlen=200)))
    if not prices:
        prices = [100.0]
    results: List[StrategySignal] = []
    ctx = {
        "sl_pct_default": state.get("spot", {}).get("sl_pct_default", 0.15),
        "tp_pct_default": state.get("spot", {}).get("tp_pct_default", 0.30),
        "reference_prices": {symbol: prices},
    }
    for _ in range(max(days, 1)):
        outputs = func(symbol, prices, ctx)
        results.extend(outputs)
        prices.append(prices[-1] * 1.001)
    pnl_estimate = sum(signal.take_pct - signal.stop_pct for signal in results)
    payload = {
        "strategy": strategy,
        "symbol": symbol,
        "trades": len(results),
        "pnl_estimate_pct": pnl_estimate,
    }
    return jsonify(payload)


@app.post("/trade/spot/demo")
@_measure_latency
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
def trade_spot_demo() -> Any:
    logger.info("/trade/spot/demo called")
    try:
        data = TradeRequest.parse_obj(request.get_json(force=True))
    except ValidationError as exc:
        logger.warning("Validation error: %s", exc)
        return jsonify({"error": exc.errors()}), 400
    except Exception as exc:  # pragma: no cover - fallback
        logger.error("Unexpected error parsing request: %s", exc)
        return jsonify({"error": str(exc)}), 400

    result = agent.place_spot_order(data.symbol, data.side, data.qty)
    status_code = 200 if result.get("ok") else 400
    logger.info("/trade/spot/demo completed status=%s", status_code)
    _audit("trade_spot_demo", ok=result.get("ok", False), details=result)
    return jsonify(result), status_code


@app.post("/trade/futures/demo")
@_measure_latency
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
def trade_futures_demo() -> Any:
    logger.info("/trade/futures/demo called")
    try:
        data = FuturesTradeRequest.parse_obj(request.get_json(force=True))
    except ValidationError as exc:
        logger.warning("Futures validation error: %s", exc)
        return jsonify({"error": exc.errors()}), 400
    except Exception as exc:  # pragma: no cover - fallback
        logger.error("Unexpected error parsing futures request: %s", exc)
        return jsonify({"error": str(exc)}), 400

    price = futures_client.get_price(data.symbol)
    leverage = float(data.leverage)
    order_value = price * data.qty
    ok, reason = futures_risk.validate_order(
        equity_usd=agent.default_equity_usd,
        order_value_usd=order_value,
        leverage=leverage,
    )

    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "symbol": data.symbol,
        "side": data.side,
        "qty": data.qty,
        "price": price,
        "leverage": leverage,
        "status": "REJECTED" if not ok else "PENDING",
        "reason": reason,
        "mode": "futures",
    }

    if not ok:
        orders_rejected_total.labels(symbol=data.symbol, side=data.side, reason=reason).inc()
        agent._log_trade(record)
        return jsonify({"ok": False, "reason": reason}), 400

    if leverage > 0:
        futures_client.set_leverage(data.symbol, int(leverage))

    order = futures_client.place_order(data.symbol, data.side, data.qty, data.type)
    orders_total.labels(symbol=data.symbol, side=data.side).inc()
    record.update({
        "status": order.get("status", "FILLED"),
        "order_id": order.get("orderId"),
        "response": order,
    })
    agent._log_trade(record)

    logger.info("/trade/futures/demo completed status=200")
    _audit("trade_futures_demo", details=order)
    return jsonify({"ok": True, "order": order})


@app.post("/ai/research/analyze_now")
@_measure_latency
@require_role("ADMIN", ops_token=OPS_TOKEN)
def ai_research_analyze_now() -> Any:
    logger.info("/ai/research/analyze_now invoked")
    payload = request.get_json(silent=True) or {}
    req = ResearchRequest.parse_obj(payload)
    results = run_research_now(req.pairs, mode="manual")
    _audit("ai_research_analyze_now", details=req.dict())
    return jsonify(ResearchResponse(results=results).dict())


def _publish_signals(signals: Iterable[SignalPayload]) -> None:
    for signal in signals:
        supervisor.bus.publish(
            "signals",
            {"symbol": signal.symbol, "side": signal.side, "qty": signal.qty},
        )


@app.post("/ai/run")
@_measure_latency
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
def run_ai() -> Any:
    logger.info("/ai/run invoked")
    decision = supervisor.get_signals()
    payload = SignalsEnvelope.parse_obj(decision)
    _publish_signals(payload.signals)
    results = agent.execute_signals(decision)
    logger.info("/ai/run completed executed=%s errors=%s", results["executed"], results["errors"])
    _audit("ai_run", details=results)
    return jsonify(results)


@app.get("/ai/signals")
@_measure_latency
def signals_feed() -> Any:
    guard = _telemetry_guard()
    if guard:
        return guard
    decision = supervisor.get_signals()
    signals = decision.get("signals", []) if isinstance(decision, dict) else []
    feed = [
        SignalFeedItem(
            ts=datetime.utcnow().isoformat(),
            symbol=str(item.get("symbol", "")),
            side=str(item.get("side", "")).upper(),
            confidence=float(item.get("score", item.get("notional_usd", 0.0))),
            strategy=str(item.get("strategy", "unknown")),
            rationale=None,
            source="supervisor",
        )
        for item in signals
    ]
    payload = SignalsFeed(items=feed, cursor=None)
    return jsonify(payload.dict())


@app.post("/signal")
@_measure_latency
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
def manual_signal() -> Any:
    logger.info("/signal invoked")
    try:
        body = request.get_json(force=True)
        if isinstance(body, dict) and "signals" in body:
            envelope = SignalsEnvelope.parse_obj(body)
        else:
            envelope = SignalsEnvelope(signals=[SignalPayload.parse_obj(body)])
    except ValidationError as exc:
        logger.warning("Signal validation error: %s", exc)
        return jsonify({"error": exc.errors()}), 400
    except Exception as exc:  # pragma: no cover
        logger.error("Unexpected error parsing signal: %s", exc)
        return jsonify({"error": str(exc)}), 400

    _publish_signals(envelope.signals)
    results = agent.execute_signals(envelope.dict())
    _audit("manual_signal", details=envelope.dict())
    return jsonify(results)


@app.get("/arbitrage/opps")
@_measure_latency
def get_arbitrage_opportunities() -> Any:
    guard = _telemetry_guard()
    if guard:
        return guard
    state = get_arbitrage_state()
    return jsonify(ArbitrageOpportunities(opportunities=state.recent(10)).dict())


@app.get("/portfolio")
@_measure_latency
def get_portfolio() -> Any:
    guard = _telemetry_guard()
    if guard:
        return guard
    logger.info("/portfolio requested")
    portfolio = agent.portfolio
    positions = [
        PortfolioPosition(
            symbol=symbol,
            quantity=pos.quantity,
            average_price=pos.average_price,
            unrealized_pnl=portfolio.unrealized_pnl(symbol),
        )
        for symbol, pos in portfolio.positions.items()
    ]
    balances = agent.client.get_balances()
    equity = portfolio.get_equity_usd({asset: bal["free"] + bal["locked"] for asset, bal in balances.items()})
    snapshot = PortfolioSnapshot(
        realized_pnl=portfolio.realized_pnl,
        unrealized_pnl=portfolio.total_unrealized(),
        positions=positions,
        equity_usd=equity,
    )
    return jsonify(snapshot.dict())


@app.get("/portfolio/snapshot")
@_measure_latency
def get_portfolio_snapshot() -> Any:
    guard = _telemetry_guard()
    if guard:
        return guard
    runtime = get_runtime_state()
    portfolio = agent.portfolio
    balances = agent.client.get_balances()
    equity = portfolio.get_equity_usd({asset: bal["free"] + bal["locked"] for asset, bal in balances.items()})
    snapshot = _capital_snapshot()
    aggregate = PortfolioAggregate(
        equity_total_usd=equity,
        tradable_equity_usd=snapshot["allocation"].tradable_equity,
        cap_pct=snapshot.get("cap_pct"),
        reserves=runtime.get("reserves", {}) if isinstance(runtime, dict) else {},
        positions=[
            PortfolioPosition(
                symbol=symbol,
                quantity=pos.quantity,
                average_price=pos.average_price,
                unrealized_pnl=portfolio.unrealized_pnl(symbol),
            )
            for symbol, pos in portfolio.positions.items()
        ],
        balances=[
            {"asset": asset, "free": data["free"], "locked": data["locked"]}
            for asset, data in balances.items()
        ],
        realized_pnl=portfolio.realized_pnl,
        unrealized_pnl=portfolio.total_unrealized(),
        timestamp=datetime.utcnow().isoformat(),
    )
    return jsonify(aggregate.dict())


@app.get("/balances")
@_measure_latency
def get_balances() -> Any:
    guard = _telemetry_guard()
    if guard:
        return guard
    logger.info("/balances requested")
    balances = agent.client.get_balances()
    response = BalancesResponse(
        balances=[
            {"asset": asset, "free": data["free"], "locked": data["locked"]}
            for asset, data in balances.items()
        ]
    )
    return jsonify(response.dict())


@app.get("/ops/logs")
@_measure_latency
def get_logs() -> Any:
    guard = _telemetry_guard()
    if guard:
        return guard
    items: List[LogEntry] = []
    if API_LOG_PATH.exists():
        try:
            lines = API_LOG_PATH.read_text(encoding="utf-8").splitlines()[-200:]
            for line in lines:
                parts = line.split(" ", 2)
                if len(parts) == 3:
                    ts, level, message = parts
                else:
                    ts, level, message = datetime.utcnow().isoformat(), "INFO", line
                items.append(LogEntry(ts=ts, level=level, message=message))
        except Exception as exc:  # pragma: no cover - IO errors
            logger.warning("Failed reading logs: %s", exc)
    payload = LogsResponse(items=list(reversed(items)))
    return jsonify(payload.dict())


@app.get("/metrics")
def metrics_endpoint() -> Response:
    return Response(scrape_metrics(), mimetype="text/plain")


if __name__ == "__main__":  # pragma: no cover
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    app.run(host=host, port=port)
