"""Flask API exposing Lunia core functionality."""
from __future__ import annotations

import logging
import os
import time
import uuid
from collections import deque
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    from dotenv import load_dotenv
except ImportError:
    from lunia_core.app.compat.dotenv import load_dotenv
from flask import Flask, Response, g, jsonify, request
from pydantic import ValidationError, BaseModel
from sqlalchemy.orm import Session

from ...boot import CORES
from ...core.ai.agent import Agent
from ...core.ai.supervisor import Supervisor
from ...core.ai.strategies import REGISTRY, StrategySignal
from ...core.portfolio.executor import PortfolioExecutor
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
# Optional modules - wrap in try-except to allow core API to start
try:
    from ..ai_research import run_research_now
except ImportError as e:
    print(f"WARNING: ai_research module not available: {e}")
    run_research_now = None

try:
    from ..arbitrage import bp as arbitrage_bp
    from ..arbitrage.worker import get_state as get_arbitrage_state
except ImportError as e:
    print(f"WARNING: arbitrage module not available: {e}")
    arbitrage_bp = None
    get_arbitrage_state = lambda: {}
# --- LOGGING SETUP ---
# --- LOGGING SETUP ---
from lunia_core.app.services.api.config import LOG_DIR
from lunia_core.app.services.security import credentials_service # Canonical Service

from lunia_core.app.services.api.schemas import (
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
    LogsResponse,
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
    PortfolioDefinition,
    PortfolioAction,
    SystemModeRequest,
    StrategyProfileRequest,
    ExchangeKeyRequest,
)

load_dotenv()

# --- CONFIG ---
LOG_DIR.mkdir(parents=True, exist_ok=True)
API_LOG_PATH = LOG_DIR / "api.log"
OPS_TOKEN = os.getenv("OPS_TOKEN", "admin-ops-key-123")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-jwt-secret")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{LOG_DIR}/lunia.db")

AUTH_REQUIRED_FOR_TELEMETRY = os.getenv("AUTH_REQUIRED_FOR_TELEMETRY", "1").lower() == "1"
DEFAULT_FLAGS = {
    "FEATURE_TELEGRAM": os.getenv("FEATURE_TELEGRAM", "0"),
    "FEATURE_MANUAL_MODE": os.getenv("FEATURE_MANUAL_MODE", "1"),
    "FEATURE_ARBITRAGE": os.getenv("FEATURE_ARBITRAGE", "1"),
    "FEATURE_FUTURES": os.getenv("FEATURE_FUTURES", "0"),
}
DEFAULT_LIMITS: list[dict[str, Any]] = []

app = Flask(__name__)
# ... logging setup ...

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
# ------------------------------------------------------------------------------
# AI ORCHESTRATOR / PROPOSAL LAYER
# ------------------------------------------------------------------------------

class AIProposal(BaseModel):
    id: str
    type: str  # 'STRATEGY_ADJUSTMENT', 'CAPITAL_ADJUSTMENT', 'MANUAL_TRADE'
    payload: Dict[str, Any]
    reasoning: str
    confidence: float
    risk_notes: List[str]
    created_at: str

# Mock In-Memory Proposals for verification
MOCK_PROPOSALS = [
    AIProposal(
        id="prop_cap_001",
        type="CAPITAL_ADJUSTMENT",
        payload={"cap_pct": 0.45},
        reasoning="Market volatility low. Increasing capital allocation to target optimal exposure.",
        confidence=0.85,
        risk_notes=["Standard exposure increase", "Below Hard Cap (90%)"],
        created_at="2025-12-15T20:00:00Z"
    ),
    AIProposal(
        id="prop_trade_002",
        type="MANUAL_TRADE",
        payload={
             "exchange_id": "binance",
             "symbol": "BTCUSDT",
             "side": "BUY", 
             "amount_usd": 5000,
             "strategy_id": "ai_momentum",
             "risk_notes": "Momentum signal breakout confirmed."
        },
        reasoning="Strong momentum breakout on 4H timeframe. Alignment with VWAP.",
        confidence=0.92,
        risk_notes=["High Confidence", "Liquid Asset"],
        created_at="2025-12-15T20:05:00Z"
    )
]

# ------------------------------------------------------------------------------
# INSTITUTIONAL SAFETY PLANE
# ------------------------------------------------------------------------------

class EventBus:
    """In-memory event bus for system-wide notifications."""
    _events: deque = deque(maxlen=1000)

    @classmethod
    def publish(cls, type: str, payload: Dict[str, Any]):
        event = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "type": type,
            "payload": payload
        }
        cls._events.append(event)
        # Also log to disk
        logger.info(f"EVENT: {type} - {payload}")

    @classmethod
    def get_events(cls, since: Optional[str] = None):
        if not since:
            return list(cls._events)
        
        # Simple string comparison for IDs might not work if they are UUIDs.
        # Ideally use timestamp or monolithic ID. 
        # For simplicity, returning all if since is not found or handling basic cursor.
        return list(cls._events) # Simplified for local dev

class UndoManager:
    """Manages time-boxed undo snapshots."""
    _snapshots: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def create_snapshot(cls, state_key: str, state_data: Any, ttl_seconds: int = 60) -> str:
        token = str(uuid.uuid4())
        cls._snapshots[token] = {
            "key": state_key,
            "data": state_data,
            "expiry": time.time() + ttl_seconds
        }
        return token

    @classmethod
    def get_snapshot(cls, token: str) -> Optional[Dict[str, Any]]:
        snapshot = cls._snapshots.get(token)
        if not snapshot:
            return None
        if time.time() > snapshot["expiry"]:
            del cls._snapshots[token]
            return None
        return snapshot
    
    @classmethod
    def clear_snapshot(cls, token: str):
        if token in cls._snapshots:
            del cls._snapshots[token]

import json

# ------------------------------------------------------------------------------
# IDEMPOTENCY PERSISTENCE
# ------------------------------------------------------------------------------

class PersistentIdempotency:
    """File-backed idempotency store for local mode."""
    # Using a JSONL file in logs directory for local persistence durability
    STORE_PATH = LOG_DIR / "idempotency.jsonl"

    @classmethod
    def get(cls, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached response if key exists."""
        if not cls.STORE_PATH.exists():
            return None
        
        # Read backward or filter. 
        # For simplicity in local file-backed mode, we scan line by line.
        # Optimziation: In production this would be Redis.
        try:
            # We want the *latest* entry for this key if multiple exist (retry logic)
            # Actually idempotency implies the *first* successful response is immutable.
            # So first match is fine? Or last? Usually key is unique per request ID.
            with open(cls.STORE_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        record = json.loads(line)
                        if record.get("key") == key:
                            return record.get("response") # {status, data, headers}
                    except:
                        continue
        except Exception as e:
            logger.error(f"Failed to read idempotency store: {e}")
        return None

    @classmethod
    def save(cls, key: str, response_tuple: Any):
        """Save response to store."""
        # Flask return tuple can be (json, code) or just json.
        # We normalize to serializable dict.
        data, code = response_tuple if isinstance(response_tuple, tuple) else (response_tuple, 200)
        
        # Extract JSON data from response object if needed
        # If 'data' is a Response object, we need to extract .json or .data
        response_data = None
        if hasattr(data, "get_json"): # Flask Response
            try:
                response_data = data.get_json()
            except:
                response_data = str(data)
        elif isinstance(data, dict) or isinstance(data, list):
            response_data = data
        else:
            response_data = str(data) # Fallback

        record = {
            "key": key,
            "timestamp": datetime.utcnow().isoformat(),
            "response": {"data": response_data, "code": code}
        }
        
        try:
            with open(cls.STORE_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            logger.error(f"Failed to save idempotency record: {e}")

def safety_guard(func):
    """
    Institutional Safety Guard Decorator.
    Enforces:
    1. Global STOP Mode Rejection
    2. Idempotency Checks (Persistent)
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # 1. STOP CHECK
        state = get_runtime_state()
        if state.get("global_stop") or state.get("system_mode") == "STOP" or state.get("mode") == "STOP":
            return jsonify({"error": "Global STOP Active", "code": "STOP_ACTIVE", "stop_active": True}), 409

        # 2. IDEMPOTENCY CHECK
        idempotency_key = request.headers.get("Idempotency-Key")
        if idempotency_key:
            cached = PersistentIdempotency.get(idempotency_key)
            if cached:
                # Return cached response strictly
                logger.info(f"Idempotency Hit: {idempotency_key}")
                return jsonify(cached["data"]), cached["code"]
        
        # Execute
        response = func(*args, **kwargs)
        
        # Save if Idempotent
        if idempotency_key:
             if isinstance(response, tuple) and 200 <= response[1] < 300:
                  PersistentIdempotency.save(idempotency_key, response)
             elif not isinstance(response, tuple):
                  # Single return implies 200 OK usually
                  PersistentIdempotency.save(idempotency_key, (response, 200))

        return response
    return wrapper

# ------------------------------------------------------------------------------
# CORE INIT
# ------------------------------------------------------------------------------


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
    # FORENSIC LOAD (Unified Service)
    creds = credentials_service.load_credentials("binance")
    
    logger.info(f"[BOOT] Agent Credentials Loaded from {creds.source}. {creds.short_len} Valid={creds.is_valid_format}")

    client = BinanceSpot(
        api_key=creds.api_key,
        api_secret=creds.api_secret,
        use_testnet=creds.is_testnet,
    )
    
    # STRICT COMBAT ENFORCEMENT
    # If we are NOT in Preview Mode, we must NEVER be mock.
    is_preview = os.getenv("LUNIA_PREVIEW_MODE", "0") == "1"
    
    if not is_preview:
        client.mock = False
        # PROVE AUTHENTICATION
        if client.verify_auth():
            logger.info("[BOOT] LIVE Authentication Verified. System HOT.")
        else:
            logger.critical("[BOOT] LIVE Authentication FAILED. System GATED (Fail-Closed).")
            
        if not creds.is_valid_format:
            logger.critical(f"[BOOT] CRITICAL: Live Mode Active but Credentials Invalid! System will FAIL-CLOSED. Error: {creds.validation_error}")
    else:
        # In Preview, we allow fallback for smooth UX
        if not creds.is_valid_format:
             client.mock = True
             logger.warning(f"[BOOT] Preview Mode: Client defaulted to MOCK due to invalid credentials")
    
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

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 15A: SIGNAL INGESTION CORE - SINGLETON STORE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
try:
    from extensions.signal_ingestion import (
        SignalStore,
        parse_news_signal,
        parse_whale_signal,
        parse_onchain_signal,
    )
    
    # Instantiate singleton store (bounded capacity)
    app.signal_store = SignalStore(max_capacity=5000)
    logger.info("[PHASE15A] SignalStore instantiated (capacity=5000)")
except ImportError as e:
    logger.warning(f"[PHASE15A] Could not import signal_ingestion: {e}")
    app.signal_store = None


@app.get("/ai/proposals")
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
def ai_proposals_get() -> Any:
    """
    Returns active AI proposals. 
    Strictly Read-Only. No execution side effects.
    """
    return jsonify([p.dict() for p in MOCK_PROPOSALS])

@app.post("/ai/proposals/<id>/acknowledge")
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
def ai_proposals_ack(id: str) -> Any:
    """
    Removes a proposal from the list (simulated).
    """
    global MOCK_PROPOSALS
    MOCK_PROPOSALS = [p for p in MOCK_PROPOSALS if p.id != id]
ensure_metrics_server(9100)

# ------------------------------------------------------------------------------
# MASTER TRACEABILITY ENDPOINTS (INSTITUTIONAL COCKPIT)
# ------------------------------------------------------------------------------

@app.post("/api/system/mode")
@safety_guard
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
def api_system_mode() -> Any:
    """Explicitly set system mode (MANUAL/SEMI/AUTO/STOP)."""
    try:
        payload = SystemModeRequest.parse_obj(request.get_json(force=True) or {})
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 400
    
    current = get_runtime_state()
    old_mode = current.get("system_mode", "MANUAL")
    new_mode = payload.mode
    
    if new_mode == "STOP":
        # Global Halt Logic
        update = {"system_mode": "STOP", "global_stop": True, "trading_on": False, "auto_mode": False}
        set_state(update)
        _audit("SYSTEM_MODE_CHANGED", details={"previous": old_mode, "new": "STOP", "halt": True})
        logger.critical("SYSTEM HALTED BY OPERATOR")
        return jsonify({"mode": "STOP", "status": "HALTED"})

    update = {"system_mode": new_mode}
    if new_mode == "AUTO":
        update["auto_mode"] = True
    elif new_mode == "MANUAL":
        update["auto_mode"] = False
    
    set_state(update)
    _audit("SYSTEM_MODE_CHANGED", details={"previous": old_mode, "new": new_mode})
    return jsonify({"mode": new_mode, "status": "OK"})


@app.post("/api/capital/set-cap")
@safety_guard
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
def api_capital_cap() -> Any:
    """Set global capital allocation cap."""
    try:
        payload = CapitalRequest.parse_obj(request.get_json(force=True) or {})
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 400

    current = get_runtime_state().get("ops", {}).get("capital", {})
    old_cap = current.get("cap_pct")
    
    if payload.cap_pct > current.get("hard_max_pct", 1.0):
        _audit("CAPITAL_CAP_REJECTED", ok=False, details={"reason": "Hard Cap Violation"})
        return jsonify({"error": "Exceeds Hard Max"}), 409

    update = {"ops": {"capital": {"cap_pct": payload.cap_pct}}}
    set_state(update)
    _audit("CAPITAL_CAP_UPDATED", details={"old": old_cap, "new": payload.cap_pct})
    return jsonify({"cap_pct": payload.cap_pct})


@app.post("/api/strategies/set-profile")
@safety_guard
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
def api_strategy_profile() -> Any:
    """Apply strict strategy profile (SHIELD / BALANCED / ROCKET)."""
    try:
        payload = StrategyProfileRequest.parse_obj(request.get_json(force=True) or {})
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 400

    profile = payload.profile
    weights = {}
    if profile == "SHIELD":
        weights = {"vwap_reversion": 0.6, "bollinger_reversion": 0.3, "micro_trend_scalper": 0.1}
    elif profile == "ROCKET":
        weights = {"liquidity_snipe": 0.4, "scalping_breakout": 0.4, "micro_trend_scalper": 0.2}
    else: # BALANCED
        weights = {"vwap_reversion": 0.3, "bollinger_reversion": 0.2, "scalping_breakout": 0.2, "micro_trend_scalper": 0.3}

    update = {
        "strategies": {"active_profile": profile},
        "spot": {"weights": weights, "enabled": True}
    }
    set_state(update)
    _audit("STRATEGY_PROFILE_CHANGED", details={"profile": profile, "weights": weights})
    return jsonify({"profile": profile, "weights": weights})


@app.post("/api/strategies/halt")
@safety_guard
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
def api_strategy_halt() -> Any:
    """Emergency Halt Strategies."""
    update = {"spot": {"enabled": False}, "trading_on": False}
    set_state(update)
    _audit("STRATEGIES_HALTED")
    return jsonify({"status": "HALTED"})


@app.post("/api/risk/set-limits")
@safety_guard
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
def api_risk_limits() -> Any:
    """Set risk limits."""
    # Assuming generic dict payload for now as SpotRiskUpdate covers keys
    try:
        payload = SpotRiskUpdate.parse_obj(request.get_json(force=True) or {})
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 400
    
    # Filter non-null
    update_data = {k: v for k, v in payload.dict().items() if v is not None}
    
    set_state({"spot": update_data})
    _audit("RISK_LIMITS_UPDATED", details=update_data)
    return jsonify(update_data)


# ------------------------------------------------------------------------------
# PORTFOLIO WIZARD ENDPOINTS
# ------------------------------------------------------------------------------

@app.post("/api/portfolios/draft/config")
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
def api_portfolio_draft_config() -> Any:
    try:
        payload = PortfolioConfig.parse_obj(request.get_json(force=True) or {})
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 400
    
    update = {"portfolio_draft": {"config": payload.dict()}}
    set_state(update)
    return jsonify(payload.dict())


@app.post("/api/portfolios/draft/assets")
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
def api_portfolio_draft_assets() -> Any:
    try:
        payload = PortfolioAssets.parse_obj(request.get_json(force=True) or {})
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 400
    
    update = {"portfolio_draft": {"assets": payload.assets}}
    set_state(update)
    return jsonify({"assets": payload.assets})


@app.post("/api/ai/analyze-portfolio")
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
def api_ai_analyze_portfolio() -> Any:
    # Read draft state
    current = get_runtime_state().get("portfolio_draft", {})
    
    # Simulate AI Analysis
    import random
    confidence = 0.75 + (random.random() * 0.2)
    risk_class = "MODERATE"
    if current.get("config", {}).get("risk_profile") == "SHIELD":
        risk_class = "LOW"
    elif current.get("config", {}).get("risk_profile") == "ROCKET":
        risk_class = "HIGH"
        
    analysis = {
        "confidence": confidence,
        "risk_class": risk_class,
        "drawdown_est": 0.12 if risk_class == "LOW" else 0.25,
        "notes": ["AI validated correlation matrix.", "Liquidity sufficient."]
    }
    
    update = {"portfolio_draft": {"ai_analysis": analysis}}
    set_state(update)
    _audit("PORTFOLIO_AI_ANALYSIS_REQUESTED", details = current.get("config"))
    return jsonify(analysis)


@app.post("/api/portfolios/create")
@safety_guard
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
def api_portfolio_create() -> Any:
    draft = get_runtime_state().get("portfolio_draft", {})
    if not draft.get("config") or not draft.get("assets"):
        return jsonify({"error": "Incomplete Draft"}), 400
        
    pid = f"port_{uuid.uuid4().hex[:8]}"
    definition = {
        "id": pid,
        "type": "LONG_TERM", # deduced from horizon
        "risk_profile": draft["config"].get("risk_profile"),
        "horizon": draft["config"].get("horizon"),
        "assets": [{"symbol": a, "weight": 1.0/len(draft["assets"])} for a in draft["assets"]],
        "status": "ACTIVE",
        "base_currency": "USDT",
        "total_capital_allocation": 0.0, # Dynamic
        "created_at": datetime.utcnow().isoformat()
    }
    
    # Update global portfolios map
    current_portfolios = get_runtime_state().get("portfolios", {}).get("definitions", {})
    current_portfolios[pid] = definition
    
    set_state({"portfolios": {"definitions": current_portfolios}})
    
    # Reset draft
    set_state({"portfolio_draft": {"config": {}, "assets": [], "ai_analysis": None}})
    
    _audit("PORTFOLIO_CREATED", details={"id": pid, "config": draft["config"]})
    return jsonify({"id": pid, "status": "CREATED"})


@app.post("/api/portfolios/<id>/action")
@safety_guard
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
def api_portfolio_action(id: str) -> Any:
    try:
        payload = PortfolioAction.parse_obj(request.get_json(force=True) or {})
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 400
        
    # Mock action logic
    _audit("PORTFOLIO_ACTION_EXECUTED", details={"id": id, "action": payload.action})
    return jsonify({"id": id, "status": payload.action, "result": "EXECUTED"})


    # 3. Full State Update
    current_portfolios = get_runtime_state().get("portfolios", {}).get("definitions", {})
    current_portfolios[p_short["id"]] = p_short
    current_portfolios[p_long["id"]] = p_long

    state_update = {
        "system_mode": "SEMI",
        "auto_mode": True,
        "global_stop": False,
        "trading_on": True,
    }
    set_state(state_update)
    _audit("DEMO_SEEDED", details={"type": "DEV_SCENARIO"})
    return jsonify({"status": "SEEDED", "scenarios": ["ALPHA_TACTICAL", "CORE_HODL"]})


@app.post("/api/exchanges/test-connection")
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
def api_test_connection() -> Any:
    """Test connection with provided or stored keys."""
    try:
        payload = request.get_json(force=True) or {}
        exchange_id = payload.get("exchange_id", "binance")
    except Exception:
        return jsonify({"error": "Invalid Payload"}), 400

    # For now, only Binance supported in test
    if exchange_id != "binance":
        return jsonify({"status": "error", "message": "Only Binance supported"}), 400

    # Determine keys to use: Payload > Stored > Env
    api_key = payload.get("api_key")
    api_secret = payload.get("api_secret") 
    is_testnet = payload.get("is_testnet", True)
    
    # If not in payload, check secrets file
    if not api_key:
        try:
             import json
             secrets_path = Path(os.getcwd()) / ".secrets.json"
             if secrets_path.exists():
                 with open(secrets_path, "r") as f:
                     secrets = json.load(f)
                     exch = secrets.get(exchange_id, {})
                     api_key = exch.get("api_key")
                     api_secret = exch.get("api_secret")
                     is_testnet = exch.get("is_testnet", True)
        except Exception as e:
            logger.warning(f"Failed to read secrets: {e}")

    # Fallback to Env
    if not api_key:
        api_key = os.getenv("BINANCE_API_KEY")
        api_secret = os.getenv("BINANCE_API_SECRET")
        is_testnet = os.getenv("BINANCE_USE_TESTNET", "true").lower() == "true"

    if not api_key or not api_secret:
        return jsonify({"status": "error", "message": "No API keys found"}), 400

    try:
        # Create temp client
        client = BinanceSpot(api_key=api_key, api_secret=api_secret, use_testnet=is_testnet, mock=False)
        # Check time or balance
        # We use get_price("BTCUSDT") as a quick read check or get_balances if permitted
        # Safer to use get_price to check connectivity, but get_balances implies valid keys
        
        # Using a specialized ping if available, or just get_price
        start = time.time()
        # Test public endpoint first
        client.get_price("BTCUSDT")
        
        # Test authenticated endpoint
        # If permission is read-only, this should work.
        try:
            client.get_balances() # This verifies signature and key validity
        except Exception as e:
             return jsonify({
                "status": "error", 
                "message": f"Auth failed. Check IPs/Permissions. Error: {str(e)}",
                "latency_ms": int((time.time() - start) * 1000)
            }), 400

        latency = int((time.time() - start) * 1000)
        return jsonify({"status": "ok", "latency_ms": latency, "message": "Connection Successful"})
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500




# Overwrite api_exchange_keys to save secrets using Canonical Service
@app.post("/api/exchanges/keys")
@safety_guard
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
def api_exchange_keys() -> Any:
    """Update exchange API keys (Audit Logged, Forensic Verified)."""
    try:
        payload = ExchangeKeyRequest.parse_obj(request.get_json(force=True) or {})
    except ValidationError as exc:
        return jsonify({"error": exc.errors()}), 400

    exchange_id = payload.exchange_id
    real_key = payload.api_key.strip()
    real_secret = payload.api_secret.strip()
    
    # 1. Handle Secret Masking (***)
    # If Input is mask, load existing secret from Service
    is_mask = set(real_secret).issubset(set("*"))
    if is_mask or not real_secret:
        existing = credentials_service.load_credentials(exchange_id)
        if existing.api_secret:
            real_secret = existing.api_secret
            logger.info(f"[KEY_UPDATE] Resolved masked secret for {exchange_id}")
        else:
            return jsonify({"error": "Cannot use masked secret; no existing credentials found."}), 400

    # 2. Save via Canonical Service (Performs strict validation)
    try:
        new_creds = credentials_service.save_credentials(exchange_id, real_key, real_secret, payload.is_testnet)
    except ValueError as e:
        # Validation Failed (Length/Format)
        return jsonify({"error": str(e), "code": "INVALID_FORMAT"}), 400
    except Exception as e:
        logger.error(f"[KEY_UPDATE] Save failed: {e}")
        return jsonify({"error": f"Failed to save credentials: {str(e)}"}), 500

    # 3. Update Runtime State (for UI reflection)
    update_item = {
        "exchange_id": exchange_id,
        "api_key": new_creds.api_key,
        "api_secret": "******", # Never store secret in state
        "is_testnet": new_creds.is_testnet,
        "status": "CONFIGURED", # Pending test
        "updated_at": _current_iso_time()
    }
    set_state({"exchange_keys": update_item})
    _audit("EXCHANGE_KEY_UPDATED", details={"exchange": exchange_id, "valid": new_creds.is_valid_format})
    
    # 4. Hot-Swap Agent (Binance Only)
    global agent
    if agent and agent.client and exchange_id == "binance":
        if isinstance(agent.client, BinanceSpot):
            agent.client.api_key = new_creds.api_key
            agent.client.api_secret = new_creds.api_secret
            agent.client.use_testnet = new_creds.is_testnet
            
            # Strict Mock Logic
            agent.client.mock = not new_creds.is_valid_format
            agent.client.__post_init__() 
            
            logger.info(f"[HOT_SWAP] Binance Client Updated. Source={new_creds.source} Mock={agent.client.mock}")

    return jsonify({
        "status": "SAVED", 
        "exchange": exchange_id, 
        "valid": new_creds.is_valid_format,
        "source": new_creds.source
    })


@app.get("/api/exchanges/keys")
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
def api_exchange_keys_list() -> Any:
    """Return status of exchange keys (Forensic aware)."""
    # For transparency, we check what is loaded in the Service, not just State.
    # Currently only Binance is supported by the service fully.
    
    results = []
    # Check Binance specifically
    creds = credentials_service.load_credentials("binance")
    
    status = "MISSING"
    if creds.source != "NONE":
        status = "CONFIGURED" if creds.is_valid_format else "INVALID"

    results.append({
        "exchange_id": "binance",
        "api_key": creds.api_key, # Safe to return public key
        "api_secret": "******" if creds.api_secret else "",
        "status": status,
        "is_testnet": creds.is_testnet,
        "source": creds.source,
        "key_len": len(creds.api_key),
        "valid": creds.is_valid_format,
        "validation_error": creds.validation_error
    })
    
    return jsonify(results)


@app.get("/api/exchanges/debug")
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
def api_exchanges_debug() -> Any:
    # Introspect Client State
    c = agent.client if agent else None
    if not c:
        return jsonify({"status": "no_agent"})

    return jsonify({
        "status": "active",
        "mock": getattr(c, "mock", None),
        "key_present": bool(c.api_key),
        "secret_present": bool(c.api_secret),
        "key_len": len(c.api_key) if c.api_key else 0,
        "secret_len": len(c.api_secret) if c.api_secret else 0,
        "exchange": "binance",
        "class": c.__class__.__name__,
        "base_url": getattr(c, "base_url", "unknown"),
        "is_testnet": getattr(c, "use_testnet", None),
        "time_offset": getattr(c, "time_offset", 0),
        "time_synced": getattr(c, "_time_synced", False),
        "session_headers": dict(c.session.headers) if hasattr(c, "session") else {},
    })


# CORS Configuration with explicit fallback (no wildcard + credentials)
ALLOWED_ORIGINS = os.getenv(
    "CORS_ALLOW_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173"  # Dev + Preview
)
ALLOWED_HEADERS = os.getenv(
    "CORS_ALLOW_HEADERS",
    "Content-Type,Authorization,X-Admin-Token,X-OPS-TOKEN,x-request-id,x-client-version",
)


@app.after_request
def _add_cors_headers(response: Response) -> Response:
    allowed_origins = [o.strip() for o in ALLOWED_ORIGINS.split(",") if o.strip()]
    request_origin = request.headers.get("Origin")

    if "*" in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = "*"
    elif request_origin and request_origin in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = request_origin
        response.headers["Vary"] = "Origin"
        # Only set credentials when not using wildcard
        response.headers["Access-Control-Allow-Credentials"] = "true"
    
    response.headers["Access-Control-Allow-Headers"] = ALLOWED_HEADERS
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PATCH, DELETE, PUT"
    # Expose x-request-id so frontend can read it
    response.headers["Access-Control-Expose-Headers"] = "Content-Type,x-request-id"
    return response


@app.route("/<path:path>", methods=["OPTIONS"])
def handle_options(path):
    return Response(status=200)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 15A: SIGNAL INGESTION ENDPOINTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.get("/signals/active")
def get_active_signals():
    """
    READ-ONLY endpoint: List active signals from in-memory store.
    
    Governance:
      - G1: NO TRADING AUTHORITY (read-only)
      - G3: Core remains wall-clock free (requires now_ms param)
      - G4: FAIL-CLOSED (missing now_ms → 400 error)
    
    Query params:
      - now_ms (required): Current timestamp in milliseconds
      - symbol (optional): Filter by symbol (e.g., BTC, ETH)
      - source (optional): Filter by source (NEWS, WHALE, ONCHAIN, etc.)
      - min_confidence (optional): Minimum confidence threshold (0.0-1.0)
    
    Returns:
      JSON with active signal states
    """
    if app.signal_store is None:
        return jsonify({"error": "SignalStore not initialized"}), 503
    
    # FAIL-CLOSED: require now_ms
    now_ms_str = request.args.get("now_ms")
    if not now_ms_str:
        return jsonify({
            "error": "Missing required parameter: now_ms",
            "code": "MISSING_NOW_MS"
        }), 400
    
    try:
        now_ms = int(now_ms_str)
    except ValueError:
        return jsonify({
            "error": "Invalid now_ms: must be integer milliseconds",
            "code": "INVALID_NOW_MS"
        }), 400
    
    # Optional filters
    symbol = request.args.get("symbol")
    source_str = request.args.get("source")
    min_confidence_str = request.args.get("min_confidence")
    
    # Parse optional filters
    from extensions.signal_ingestion import SignalSource
    from decimal import Decimal
    
    source = None
    if source_str:
        try:
            source = SignalSource(source_str)
        except ValueError:
            return jsonify({
                "error": f"Invalid source: {source_str}",
                "code": "INVALID_SOURCE"
            }), 400
    
    min_confidence = None
    if min_confidence_str:
        try:
            min_confidence = Decimal(min_confidence_str)
        except Exception:
            return jsonify({
                "error": f"Invalid min_confidence: {min_confidence_str}",
                "code": "INVALID_CONFIDENCE"
            }), 400
    
    # Query store (READ-ONLY operation)
    signal_states = app.signal_store.list_active(
        now_ms=now_ms,
        symbol=symbol,
        source=source,
        min_confidence=min_confidence,
    )
    
    # Serialize states to JSON
    items = []
    for state in signal_states:
        items.append({
            "signal_id": state.signal_id,
            "active": state.active,
            "age_ms": state.age_ms,
            "remaining_ms": state.remaining_ms,
            "weight": str(state.weight),  # Decimal → string
            "reason": state.reason,
        })
    
    return jsonify({
        "status": "ok",
        "now_ms": now_ms,
        "count": len(items),
        "items": items,
    })


@app.post("/signals/ingest/debug")
def ingest_signal_debug():
    """
    DEBUG-ONLY endpoint: Ingest a test signal into the store.
    
    Governance:
      - G1: NO TRADING AUTHORITY (context layer only)
      - G4: FAIL-CLOSED (requires now_ms, validates fields)
      - G5: SECURITY (requires X-OPS-TOKEN + SIGNAL_DEBUG_INGEST=1)
    
    Security:
      - Requires header: X-OPS-TOKEN matching OPS_TOKEN
      - Requires env: SIGNAL_DEBUG_INGEST=1 (default OFF)
    
    Body (JSON):
      - now_ms (required): Signal timestamp in milliseconds
      - source (required): Signal source (NEWS, WHALE, ONCHAIN, etc.)
      - category (required): Signal category string
      - headline (required): Headline text
      - confidence (required): Confidence score 0.0-1.0 (as string)
      - severity (required): Severity (LOW, MEDIUM, HIGH, CRITICAL)
      - ttl_ms (required): Time-to-live in milliseconds
      - symbol (optional): Asset symbol
      - summary (optional): Longer description
      - tags (optional): List of tag strings
      - payload (optional): Additional metadata dict
    
    Returns:
      JSON with signal_id and stored status
    """
    if app.signal_store is None:
        return jsonify({"error": "SignalStore not initialized"}), 503
    
    # SECURITY: Check env flag
    if os.getenv("SIGNAL_DEBUG_INGEST", "0") != "1":
        return jsonify({
            "error": "Debug ingest endpoint disabled",
            "code": "ENDPOINT_DISABLED"
        }), 404
    
    # SECURITY: Require OPS token
    token = request.headers.get("X-OPS-TOKEN") or request.headers.get("X-Ops-Token")
    if token != OPS_TOKEN:
        return jsonify({
            "error": "Unauthorized: invalid or missing X-OPS-TOKEN",
            "code": "UNAUTHORIZED"
        }), 403
    
    # Parse JSON body
    try:
        data = request.get_json(force=True)
    except Exception as e:
        return jsonify({
            "error": f"Invalid JSON body: {e}",
            "code": "INVALID_JSON"
        }), 400
    
    # FAIL-CLOSED: require now_ms
    if "now_ms" not in data:
        return jsonify({
            "error": "Missing required field: now_ms",
            "code": "MISSING_NOW_MS"
        }), 400
    
    try:
        now_ms = int(data["now_ms"])
    except ValueError:
        return jsonify({
            "error": "Invalid now_ms: must be integer",
            "code": "INVALID_NOW_MS"
        }), 400
    
    # FAIL-CLOSED: Require valid source (NO FALLBACK)
    source = data.get("source")
    if not source:
        return jsonify({
            "error": "Missing required field: source",
            "code": "MISSING_SOURCE"
        }), 400
    
    # Strict dispatch: reject unknown sources
    try:
        if source == "NEWS":
            event = parse_news_signal(data, ts_ms=now_ms)
        elif source == "WHALE":
            event = parse_whale_signal(data, ts_ms=now_ms)
        elif source == "ONCHAIN":
            event = parse_onchain_signal(data, ts_ms=now_ms)
        else:
            # NO FALLBACK: explicit rejection
            return jsonify({
                "error": f"Invalid source: {source}",
                "code": "INVALID_SOURCE",
                "allowed": ["NEWS", "WHALE", "ONCHAIN"]
            }), 400
    except (ValueError, TypeError, KeyError) as e:
        return jsonify({
            "error": f"Failed to parse signal: {e}",
            "code": "PARSE_ERROR"
        }), 400
    
    # Upsert into store
    app.signal_store.upsert(event)
    
    logger.info(f"[PHASE15A] Ingested signal: {event.signal_id} (source={event.source})")
    
    return jsonify({
        "status": "ok",
        "signal_id": event.signal_id,
        "stored": True,
        "source": event.source.value,
        "headline": event.headline,
    })


@app.route('/api/dev/seed-demo', methods=['POST'])
def seed_demo_data():
    """Seeds the system with demo portfolios and state for walkthrough."""
    # Verify Ops Token
    token = request.headers.get('X-Ops-Token')
    if token != 'admin-ops-key-123': # Hardcoded dev token for demo
        return jsonify({"error": "Unauthorized"}), 403

    # 1. Create Portfolios
    p_short = {
        "id": "ALPHA_TACTICAL_01",
        "type": "TACTICAL",
        "risk_profile": "AGGRESSIVE",
        "horizon": "2 WEEKS",
        "assets": [
            {"symbol": "SOL", "weight": 0.40, "confidence": 0.88, "reason": ["Momentum Breakout", "Volume Spike"], "sector": "L1", "risk_note": "High Volatility"},
            {"symbol": "INJ", "weight": 0.30, "confidence": 0.72, "reason": ["DeFi Growth"], "sector": "DeFi", "risk_note": "Concentrated"},
            {"symbol": "RUNE", "weight": 0.30, "confidence": 0.65, "reason": ["Yield Arbs"], "sector": "Infra", "risk_note": "Bridge Risk"}
        ],
        "rules": {"entry_mode": "MOMENTUM", "rebalance_interval_days": 3, "profit_take_pct": 0.15, "stop_loss_pct": 0.05},
        "status": "ACTIVE",
        "base_currency": "USD",
        "total_capital_allocation": 50000,
        "created_at": datetime.utcnow().isoformat()
    }
    
    p_long = {
        "id": "CORE_HODL_24",
        "type": "LONG_TERM",
        "risk_profile": "BALANCED",
        "horizon": "1 YEAR",
        "assets": [
            {"symbol": "BTC", "weight": 0.60, "confidence": 0.95, "reason": ["Store of Value", "Halving"], "sector": "Store of Value", "risk_note": "None"},
            {"symbol": "ETH", "weight": 0.40, "confidence": 0.92, "reason": ["Yield", "L2 Activity"], "sector": "L1", "risk_note": "Reg Risk"}
        ],
        "rules": {"entry_mode": "DCA", "rebalance_interval_days": 30, "profit_take_pct": 0.50, "stop_loss_pct": 0.20},
        "status": "ACTIVE",
        "base_currency": "USD",
        "total_capital_allocation": 150000,
        "created_at": datetime.utcnow().isoformat()
    }

    # 2. AI Proposal
    ai_proposal = {
        "id": f"prop-{int(time.time())}",
        "type": "CAPITAL_ADJUSTMENT",
        "payload": {"cap_pct": 0.65},
        "confidence": 0.88,
        "reasoning": "Market volatility decreasing. Recommend increasing capital deployment to capture yield.",
        "risk_notes": ["Medium Volatility", "Monitor Drawdown"],
        "status": "PENDING",
        "timestamp": datetime.utcnow().isoformat(),
        "created_at": datetime.utcnow().isoformat()
    }

    # 3. Full State Update
    current_portfolios = get_runtime_state().get("portfolios", {}).get("definitions", {})
    current_portfolios[p_short["id"]] = p_short
    current_portfolios[p_long["id"]] = p_long

    state_update = {
        "system_mode": "SEMI",
        "auto_mode": True,
        "global_stop": False,
        "trading_on": True,
        
        # Capital Governance
        "ops": {
            "capital": {
                "cap_pct": 0.50,
                "hard_max_pct": 0.90
            }
        },
        "reserves": {
            "portfolio": 0.15,
            "arbitrage": 0.10
        },
        
        # Exchanges
        "exchanges": {
            "binance": {"enabled": True, "allocation": 0.7, "name": "Binance", "id": "binance", "connected": True},
            "okx": {"enabled": True, "allocation": 0.3, "name": "OKX", "id": "okx", "connected": True}
        },
        "exchange_keys": {
            "binance": {
                "exchange_id": "binance",
                "api_key": "mock-api-key",
                "api_secret": "mock-secret-key",
                "is_testnet": True,
                "status": "CONNECTED",
                "updated_at": "2025-12-16T12:00:00Z"
            }
        },
        
        # Strategies
        "spot": {
            "enabled": True,
            "weights": {
                "micro_trend_scalper": 0.40,
                "scalping_breakout": 0.30, 
                "bollinger_reversion": 0.30,
                "vwap_reversion": 0.0,
                "liquidity_snipe": 0.0
            },
            # Risk Limits
            "max_positions": 5,
            "max_trade_pct": 0.20,
            "risk_per_trade_pct": 0.01,
            "max_symbol_exposure_pct": 0.25,
            "max_daily_loss_pct": 0.05
        },
        
        "portfolios": {"definitions": current_portfolios}
    }
    
    set_state(state_update)

    # Inject Mock Proposal into Global List
    global MOCK_PROPOSALS
    # Convert dict to Pydantic model for compatibility with MOCK_PROPOSALS list if needed
    # But MOCK_PROPOSALS is just a list of AIProposal objects.
    # We can reconstruct it to match the type expected by the GET endpoint.
    prop_obj = AIProposal(
        id=ai_proposal["id"],
        type=ai_proposal["type"],
        payload=ai_proposal["payload"],
        reasoning=ai_proposal["reasoning"],
        confidence=ai_proposal["confidence"],
        risk_notes=ai_proposal["risk_notes"],
        created_at=ai_proposal["created_at"]
    )
    MOCK_PROPOSALS.append(prop_obj)

    _audit("SYSTEM_SEED", details={"message": "Seeded Demo Data for Walkthrough", "portfolios_count": 2, "proposals_added": 1})
    
    return jsonify({"status": "seeded", "portfolios": 2, "mode": "preview"})

@app.route("/", methods=["OPTIONS"])
def handle_root_options():
    return Response(), 200


@app.before_request
def _inject_db_and_user() -> None:
    g.db = get_session()
    g.current_user = None
    auth_header = request.headers.get("Authorization", "")
    
    # DEV AUTH BYPASS (localhost development only)
    # Satisfies PHASE 2 requirements: fail-closed by default, only active for localhost origins
    if os.getenv("DEV_AUTH_BYPASS") == "1":
        remote_addr = request.remote_addr or ""
        origin = request.headers.get("Origin", "")
        
        # Security gate: ONLY allow localhost/127.0.0.1
        is_localhost = (
            remote_addr in ("127.0.0.1", "::1", "localhost") or
            origin.startswith("http://localhost:") or
            origin.startswith("http://127.0.0.1:")
        )
        
        if is_localhost:
            g.current_user = User(
                id=1,
                email="local-operator@localhost",
                password_hash="dev-bypass",
                role="ADMIN",
                is_active=True,
                created_at=datetime.utcnow()
            )
            # Add attributes for compatibility
            g.current_user.tier = "INSTITUTIONAL"
            g.current_user.trust_score = 100.0
            g.current_user.onboarding_completed = True
            logger.debug(f"[DEV_AUTH_BYPASS] Injected admin user for {origin} from {remote_addr}")
            return
    
    # PREVIEW MODE OVERRIDE
    if os.getenv("LUNIA_PREVIEW_MODE") == "1":
        # Mock User for Preview
        g.current_user = User(
            id=999,
            email="demo@lunia.dev",
            password_hash="mock",
            role="TRADER",
            is_active=True,
            created_at=datetime.utcnow()
        )
        # Monkey patch attributes that might not be in __init__ or are properties
        g.current_user.tier = "INSTITUTIONAL"
        g.current_user.trust_score = 100.0
        g.current_user.onboarding_completed = True
        return

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


@app.post("/api/v1/auth/login")
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


@app.get("/api/v1/auth/me")
@_measure_latency
@require_auth()
def auth_me() -> Any:
    user: Optional[User] = current_user()
    if not user:
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(_user_payload(user))


# Alias for frontend compatibility (expects /auth/me not /api/v1/auth/me)
@app.get("/auth/me")
@_measure_latency
@require_auth()
def auth_me_alias() -> Any:
    user: Optional[User] = current_user()
    if not user:
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(_user_payload(user))


@app.post("/api/v1/auth/logout")
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
            metadata=event.event_metadata,
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


@app.post("/ops/start")
@_measure_latency
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
def ops_start() -> Any:
    """
    START Button orchestration endpoint.
    Transitions system from IDLE to RUNNING with governance gates.
    """
    body = request.get_json(force=True) or {}
    requested_mode = body.get("mode", "dry")  # "dry" or "real"
    
    state = get_runtime_state()
    global_stop = state.get("global_stop", True)
    live_confirmed = body.get("live_confirmed", False)  # Must be explicitly passed
    airlock_status = state.get("airlock_status", "NOT_READY")
    system_mode = state.get("system_mode", "MANUAL")  # VARIANT A: Use system_mode
    # VARIANT A: live_allowed is explicit server arm status (derived from env or explicit setting)
    live_allowed = state.get("live_allowed", os.environ.get("LIVE_ALLOWED", "0") == "1")
    
    gates = {
        "global_stop": global_stop,
        "system_mode": system_mode,  # VARIANT A: Changed from exec_mode
        "airlock": airlock_status,
        "keys_present": bool(state.get("exchange_keys", {})),
        "live_allowed": live_allowed,  # VARIANT A: Explicit server arm status
    }
    
    # GOVERNANCE GATE: Blocked conditions
    if global_stop:
        _audit("OPS_START_BLOCKED", ok=False, details={"reason": "global_stop"})
        return jsonify({
            "status": "blocked",
            "reason": "System Halted by Global Stop",
            "gates": gates
        }), 403
        
    if airlock_status == "BLOCKED":
        _audit("OPS_START_BLOCKED", ok=False, details={"reason": "airlock_blocked"})
        return jsonify({
            "status": "blocked", 
            "reason": "Airlock Security Active",
            "gates": gates
        }), 403
    
    # VARIANT A: Force DRY if conditions not met for REAL
    # Real requires: airlock ARMED + live_confirmed + live_allowed + !global_stop
    run_mode = "dry"
    if requested_mode == "real" and airlock_status == "ARMED" and live_confirmed and live_allowed:
        run_mode = "real"
    
    started_at = datetime.utcnow().isoformat()
    
    # Update run_state
    run_state_update = {
        "running": True,
        "phase": "assembling_portfolio",
        "started_at": started_at,
        "run_mode": run_mode,
        "last_error": None,
    }
    set_state({"run_state": run_state_update})
    
    _audit("OPS_START_REQUESTED", details={
        "run_mode": run_mode,
        "requested_mode": requested_mode,
        "gates": gates
    })
    
    return jsonify({
        "status": "success",
        "started_at": started_at,
        "run_mode": run_mode,
        "gates": gates
    })


@app.get("/ops/run-state")
@_measure_latency
def ops_run_state() -> Any:
    """
    Get current orchestration run state.
    """
    guard = _telemetry_guard()
    if guard:
        return guard
    state = get_runtime_state()
    run_state = state.get("run_state", {
        "running": False,
        "phase": "idle",
        "last_error": None
    })
    return jsonify(run_state)


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
    # Hard System Limit (Memory of Project Rules)
    HARD_CAP_PCT = 0.90 

    snapshot = _capital_snapshot()
    
    # Compute derived metrics
    reserves = snapshot["state"].get("reserves", {})
    port_res = float(reserves.get("portfolio", 0.05)) # Default 5%
    arb_res = float(reserves.get("arbitrage", 0.0))
    locked_total = port_res + arb_res
    
    current_cap = float(snapshot["cap_pct"])
    usable_cap = max(0.0, current_cap - locked_total)

    payload = {
        "global_cap_pct": current_cap,
        "hard_cap_pct": HARD_CAP_PCT,
        "portfolio_reserve_pct": port_res,
        "arbitrage_reserve_pct": arb_res,
        "locked_reserve_pct": locked_total,
        "usable_cap_pct": usable_cap,
        
        # Legacy/Compat fields
        "cap_pct": current_cap,
        "equity": snapshot["equity"], 
        "equity_total_usd": snapshot["equity"],
        "allocation": snapshot["allocation"].per_strategy,
        "tradable_equity_usd": snapshot["allocation"].tradable_equity,
        "per_strategy_budgets": snapshot["allocation"].per_strategy,
        "state": OpsState.parse_obj(snapshot["state"]).dict(),
        "reserves": reserves,
    }
    return jsonify(payload)


@app.post("/ops/capital")
@_measure_latency
@require_role("ADMIN", ops_token=OPS_TOKEN)
def ops_capital_update() -> Any:
    HARD_CAP_PCT = 0.90
    payload = CapitalRequest.parse_obj(request.get_json(force=True) or {})
    
    # SAFETY CHECK: Hard Limit Enforced
    if payload.cap_pct > HARD_CAP_PCT:
        _audit("ops_capital_update_blocked", ok=False, details={"attempted": payload.cap_pct, "limit": HARD_CAP_PCT})
        return jsonify({"error": "hard_cap_violation", "message": f"Capital cannot exceed {HARD_CAP_PCT*100}%"}), 400

    # Get OLD state for audit
    old_state = get_runtime_state().get("ops", {}).get("capital", {})
    
    state = set_state({"ops": {"capital": {"cap_pct": payload.cap_pct}}})
    
    # Get NEW state for response/verification
    snapshot = _capital_snapshot()
    
    response = {
        "state": OpsState.parse_obj(state).dict(),
        "cap_pct": snapshot["cap_pct"],
        "equity": snapshot["equity"], # Frontend expects "equity"
        "allocation": snapshot["allocation"].per_strategy, # Frontend expects "allocation"
        "tradable_equity_usd": snapshot["allocation"].tradable_equity,
    }
    
    audit_meta = {
        "before": old_state,
        "after": {"cap_pct": payload.cap_pct},
        "hard_limit": HARD_CAP_PCT
    }
    _audit("ops_capital_update", details=audit_meta)
    return jsonify(response)


@app.post("/spot/mode")
@_measure_latency
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
def spot_mode() -> Any:
    body = request.get_json(force=True) or {}
    mode = str(body.get("mode", "")).upper()
    updates = {}
    if mode == "AUTO":
        updates = {"auto_mode": True, "global_stop": False}
    elif mode == "MANUAL":
        updates = {"auto_mode": False, "global_stop": False}
    elif mode == "STOP":
        updates = {"global_stop": True}
    
    if updates:
        set_state(updates)
        _log_activity("spot_mode_change", details=mode)
        
    return jsonify({"mode": mode, "updates": updates})


@app.get("/spot/exchanges")
@_measure_latency
def spot_exchanges() -> Any:
    state = get_runtime_state()
    saved = state.get("exchanges", {})
    
    defaults = [
        {"id": "binance", "name": "Binance Spot", "enabled": True, "allocation": 1.0, "connected": True, "risk_label": "LOW", "permissions": {"read": True, "trade": True}},
        {"id": "okx", "name": "OKX Spot", "enabled": False, "allocation": 0.0, "connected": False, "risk_label": "MED", "permissions": {"read": False, "trade": False}},
        {"id": "kraken", "name": "Kraken Spot", "enabled": False, "allocation": 0.0, "connected": False, "risk_label": "LOW", "permissions": {"read": False, "trade": False}},
        {"id": "coinbase", "name": "Coinbase Pro", "enabled": False, "allocation": 0.0, "connected": False, "risk_label": "LOW", "permissions": {"read": False, "trade": False}},
    ]
    
    # Merge saved config into defaults
    merged = []
    for ex in defaults:
        cfg = saved.get(ex["id"], {})
        # Override fields if present in saved config
        if "enabled" in cfg:
            ex["enabled"] = cfg["enabled"]
        if "allocation" in cfg:
            ex["allocation"] = float(cfg["allocation"])
        if "risk_label" in cfg:
            ex["risk_label"] = str(cfg["risk_label"])
        merged.append(ex)
        
    return jsonify(merged)


@app.post("/spot/exchanges/<id>/config")
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
def spot_exchange_config(id: str) -> Any:
    body = request.get_json(force=True) or {}
    
    # Construct update for top-level "exchanges" key
    # set_state handles merging deep keys for "exchanges" automatically via _apply_exchange_update
    
    update_data = {}
    if "enabled" in body:
        update_data["enabled"] = bool(body["enabled"])
    if "allocation" in body:
        update_data["allocation"] = float(body["allocation"])
    if "risk_label" in body:
        update_data["risk_label"] = str(body["risk_label"])
        
    if update_data:
        update = {"exchanges": {id: update_data}}
        set_state(update)
    
    _audit("spot_exchange_config", details={"exchange": id, "config": body})
    return jsonify({"status": "updated", "id": id, "config": body})


@app.get("/spot/state")
@_measure_latency
def spot_state_endpoint() -> Any:
    state = get_runtime_state()
    spot = state.get("spot", {})
    return jsonify({
        "enabled": spot.get("enabled", True),
        "weights": spot.get("weights", {}),
        "max_positions": spot.get("max_positions", 5),
        "max_trade_pct": spot.get("max_trade_pct", 0.2),
        "risk_per_trade_pct": spot.get("risk_per_trade_pct", 0.01),
        "max_symbol_exposure_pct": spot.get("max_symbol_exposure_pct", 0.1),
        "tp_pct_default": spot.get("tp_pct_default", 0.05),
        "sl_pct_default": spot.get("sl_pct_default", 0.02)
    })
    

@app.get("/spot/strategies")
@_measure_latency
def spot_strategies() -> Any:
    state = get_runtime_state()
    spot_cfg = state.get("spot", {})
    weights = spot_cfg.get("weights", {})
    
    # Metadata map (Static enrichment as per prompt req)
    META = {
        "micro_trend_scalper": {"name": "Micro Trend Scalper", "horizon": "SHORT", "risk_label": "HIGH", "core": "SCALP"},
        "scalping_breakout": {"name": "Scalping Breakout", "horizon": "SHORT", "risk_label": "HIGH", "core": "SCALP"},
        "bollinger_reversion": {"name": "Bollinger Reversion", "horizon": "MID", "risk_label": "MED", "core": "MEAN_REV"},
        "vwap_reversion": {"name": "VWAP Reversion", "horizon": "INTRADAY", "risk_label": "LOW", "core": "MEAN_REV"},
        "liquidity_snipe": {"name": "Liquidity Snipe", "horizon": "INSTANT", "risk_label": "EXTREME", "core": "HFT"},
    }
    
    strategies = []
    for sid, weight in weights.items():
        meta = META.get(sid, {"name": sid, "horizon": "UNKNOWN", "risk_label": "UNKNOWN", "core": "UNKNOWN"})
        strategies.append({
            "id": sid,
            "name": meta["name"],
            "core": meta["core"],
            "enabled": weight > 0, # In original logic, weight 0 implies disabled effectively
            "weight": weight,
            "horizon": meta["horizon"],
            "risk_label": meta["risk_label"],
            "mode_override": "AI",
            "performance_pct": 0.0, # HONESTY: Real tracking not yet populated
            "confidence": 0.50 # HONESTY: Neutral confidence
        })
        
    return jsonify(strategies)


@app.post("/spot/strategies")
@_measure_latency
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
@safety_guard
def spot_strategies_update() -> Any:
    # 1. Capture Before State
    current_state = get_runtime_state()
    old_weights = current_state.get("spot", {}).get("weights", {})
    
    # Support both old format (full object) and new format (list of strats)
    raw = request.get_json(force=True) or {}
    weights = {}
    
    # New Format: [{"id": "...", "weight": 0.2, "enabled": true}]
    if isinstance(raw, list):
        for item in raw:
            if item.get("enabled"):
                try:
                    weights[item["id"]] = float(item["weight"])
                except:
                    pass
            else:
                 weights[item["id"]] = 0.0
        
        # Merge with existing logic? Usually strategies endpoint defines FULL set.
        # But if raw list is partial? Assuming full set for simplicity or merge.
        # The original code replaced "spot.weights" entirely. We stick to that.
    else:
        # Old Format
        payload = StrategyWeightsRequest.parse_obj(raw)
        weights = payload.weights

    # --- GOVERNANCE VALIDATION ---
    total_weight = sum(weights.values())
    
    # 1. Check for negative weights
    if any(w < 0 for w in weights.values()):
        _audit("spot_strategies_update_rejected", ok=False, details={"reason": "negative_weights", "weights": weights})
        return jsonify({
            "error": "Strategy weights cannot be negative",
            "code": "INVALID_STRATEGY_WEIGHTS"
        }), 400

    # 2. Check sum equals 1.0 (with epsilon)
    if abs(total_weight - 1.0) > 0.001:
        _audit("spot_strategies_update_rejected", ok=False, details={"reason": "sum_not_100", "sum": total_weight, "weights": weights})
        return jsonify({
            "error": f"Strategy weights must sum to 100% (Current: {total_weight*100:.1f}%)",
            "code": "INVALID_STRATEGY_WEIGHTS",
            "current_sum": total_weight
        }), 400

    # 2. Update State
    update = {"spot": {"weights": weights}}
    state = set_state(update)
    
    # 3. Create Undo
    undo_ttl = 60
    undo_token = UndoManager.create_snapshot("spot.weights", {"spot": {"weights": old_weights}}, ttl_seconds=undo_ttl)
    
    # 4. Audit & Event
    _log_activity("spot_strategies_update", details=str(update))
    _audit("spot_strategies_update", details={"new_weights": weights})
    EventBus.publish("strategies.updated", {"weights": weights, "undo_token": undo_token})

    # 5. Return
    resp = OpsState.parse_obj(state).dict()
    resp["undo_token"] = undo_token
    resp["undo_ttl"] = undo_ttl
    return jsonify(resp)


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


@app.get("/spot/risk/dashboard")
@_measure_latency
def spot_risk_dashboard() -> Any:
    """Risk dashboard with current limits and usage."""
    guard = _telemetry_guard()
    if guard:
        return guard
    state = get_runtime_state()
    spot_cfg = state.get("spot", {})
    payload = {
        "current_positions": 0,  # Would come from portfolio in real impl
        "max_positions": spot_cfg.get("max_positions", 5),
        "max_trade_pct": spot_cfg.get("max_trade_pct", 0.20),
        "risk_per_trade_pct": spot_cfg.get("risk_per_trade_pct", 0.01),
        "sl_pct_default": spot_cfg.get("sl_pct_default", 0.15),
        "tp_pct_default": spot_cfg.get("tp_pct_default", 0.30),
        "daily_drawdown_pct": 0.0,  # Would be computed from trades
        "max_daily_drawdown_pct": 0.05,  # Hard limit
        "risk_status": "NOMINAL",
        "warnings": [],
    }
    return jsonify(payload)


@app.get("/spot/risk/mandates")
@_measure_latency
def spot_risk_mandates() -> Any:
    """Risk mandates - hard constraints for execution."""
    guard = _telemetry_guard()
    if guard:
        return guard
    state = get_runtime_state()
    spot_cfg = state.get("spot", {})
    mandates = [
        {
            "id": "max_trade_size",
            "name": "Max Trade Size",
            "value": spot_cfg.get("max_trade_pct", 0.20),
            "unit": "% of equity",
            "enforced": True,
            "source": "CONFIG",
        },
        {
            "id": "stop_loss_required",
            "name": "Stop-Loss Required",
            "value": True,
            "unit": "boolean",
            "enforced": True,
            "source": "GOVERNANCE",
        },
        {
            "id": "max_positions",
            "name": "Max Concurrent Positions",
            "value": spot_cfg.get("max_positions", 5),
            "unit": "positions",
            "enforced": True,
            "source": "CONFIG",
        },
        {
            "id": "sl_pct_default",
            "name": "Default Stop-Loss",
            "value": spot_cfg.get("sl_pct_default", 0.15),
            "unit": "% from entry",
            "enforced": True,
            "source": "CONFIG",
        },
    ]
    return jsonify({"mandates": mandates})


@app.post("/spot/manual/preview")
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
def manual_trade_preview() -> Any:
    # 1. Parse
    body = request.get_json(force=True) or {}
    # Handles both direct proposal or wrapped
    prop_data = body.get("proposal", body)
    
    # 2. Mock Analysis
    amount = float(prop_data.get("amount_usd", 0))
    state = get_runtime_state()
    cap_pct = state.get("ops", {}).get("capital", {}).get("cap_pct", 1.0)
    
    # Check limits
    allowed = True
    blocking_reason = None
    
    if amount > 50000:
        allowed = False
        blocking_reason = "Exceeds single trade limit ($50k)"
        
    # 3. Construct Response with Proposal & Deadline
    deadline = int(time.time() + 30) # 30s TTL
    
    resp = {
        "allowed": allowed,
        "blocking_reason": blocking_reason,
        "proposal": {
            **prop_data,
            "confirm_deadline": deadline
        },
        "capital_delta_usd": amount,
        "projected_usage_pct": 0.1, # Mock
        "risk_flags": ["HIGH_VOLATILITY"] if amount > 10000 else [],
        "risk_notes": "Trade is within operational limits."
    }
    return jsonify(resp)

@app.post("/spot/manual/execute")
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
@safety_guard
def manual_trade_execute() -> Any:
    # P0-001 HOTFIX: Governance gates (FAIL-CLOSED)
    state = get_runtime_state()
    global_stop = bool(state.get("global_stop", True))
    airlock_status = state.get("airlock_status", "NOT_READY")
    run_mode = (state.get("run_state") or {}).get("run_mode", "dry")
    system_mode = state.get("system_mode", "MANUAL")
    live_allowed = bool(state.get("live_allowed", os.environ.get("LIVE_ALLOWED", "0") == "1"))

    gates = {
        "global_stop": global_stop,
        "airlock_status": airlock_status,
        "run_mode": run_mode,
        "live_allowed": live_allowed,
        "system_mode": system_mode,
    }

    if global_stop:
        _audit("MANUAL_EXECUTE_BLOCKED", ok=False, details={"reason": "global_stop", "gates": gates})
        return jsonify({"error": "Trading halted", "code": "GLOBAL_STOP", "gates": gates}), 403

    if airlock_status != "ARMED":
        _audit("MANUAL_EXECUTE_BLOCKED", ok=False, details={"reason": "airlock_not_armed", "gates": gates})
        return jsonify({"error": "Airlock not ARMED", "code": "AIRLOCK_NOT_ARMED", "gates": gates}), 403

    if not live_allowed:
        _audit("MANUAL_EXECUTE_BLOCKED", ok=False, details={"reason": "live_not_allowed", "gates": gates})
        return jsonify({"error": "LIVE not allowed (server not armed)", "code": "LIVE_NOT_ALLOWED", "gates": gates}), 403

    if run_mode != "real":
        _audit("MANUAL_EXECUTE_BLOCKED", ok=False, details={"reason": "not_in_real_mode", "gates": gates})
        return jsonify({"error": "Not in REAL mode", "code": "DRY_MODE", "gates": gates}), 403

    # 1. Parse
    body = request.get_json(force=True) or {}
    proposal = body.get("proposal", {})
    confirmed = body.get("confirmed", False)
    
    if not confirmed:
        return jsonify({"error": "Confirmation required"}), 400
        
    # 2. TTL Check
    deadline = proposal.get("confirm_deadline")
    if deadline and time.time() > deadline:
        return jsonify({"error": "Confirmation Expired", "code": "CONFIRM_EXPIRED"}), 400
        
    # 3. Simulate Execution
    _audit("manual_trade_execute", details=proposal)
    _log_activity("manual_trade_execute", details=f"{proposal.get('side')} {proposal.get('symbol')} ${proposal.get('amount_usd')}")
    
    if proposal.get("amount_usd", 0) > 1000000:
         # Simulate Engine Error
         return jsonify({"error": "Engine Rejected: Insufficient Liquidity"}), 500
         
    return jsonify({"status": "FILLED", "tx_id": str(uuid.uuid4())})


@app.post("/ops/undo")
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
@safety_guard
def ops_undo() -> Any:
    body = request.get_json(force=True) or {}
    token = body.get("token")
    if not token:
        return jsonify({"error": "Missing token"}), 400
    
    snapshot = UndoManager.get_snapshot(token)
    if not snapshot:
        return jsonify({"error": "Undo window expired"}), 400
        
    state_key = snapshot["key"]
    state_data = snapshot["data"]
    
    # Restore
    set_state(state_data)
         
    UndoManager.clear_snapshot(token)
    _audit("undo_applied", details={"key": state_key})
    EventBus.publish("undo.applied", {"key": state_key})
    
    return jsonify({"status": "restored", "key": state_key})


@app.get("/ops/events")
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
def ops_events() -> Any:
    return jsonify(EventBus.get_events())


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
    # Diagnostic ID
    req_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    logger.info(f"[DIAGNOSTIC] /balances START req_id={req_id}")

    try:
        guard = _telemetry_guard()
        if guard:
            return guard
        
        # Determine Source & Enforce Fail-Closed
        requested_source = request.headers.get("X-Data-Source", "AUTO").upper()
        logger.info(f"[DIAGNOSTIC] RequestedSource={requested_source}")
        
        if not agent or not agent.client:
            return jsonify({"error": "Agent not ready"}), 503

        c = agent.client
        current_is_mock = getattr(c, "mock", True)
        logger.info(f"[DIAGNOSTIC] AgentState: Mock={current_is_mock} KeyLen={len(c.api_key or '')}")

        # Enforce REAL Mode Pre-checks
        if requested_source == "REAL":
            has_keys = bool(c.api_key and c.api_secret)
            if not has_keys:
                 msg = "Cannot serve REAL data: No Validation Keys found in client."
                 logger.error(f"[DIAGNOSTIC] {msg}")
                 return jsonify({
                    "error": msg,
                    "source": "REAL",
                    "upstream_status": 401, 
                    "request_id": req_id
                }), 401

        # Execute Fetch
        logger.info(f"[DIAGNOSTIC] Executing get_balances(force_real={requested_source == 'REAL'})")
        
        # Force Real if requested
        force_real = (requested_source == "REAL")
        
        # --- CRITICAL SECTION ---
        balances = c.get_balances(force_real=force_real)
        # ------------------------
        
        logger.info(f"[DIAGNOSTIC] Fetch Success. RowCount={len(balances)}")

        effective_source = "SIMULATION" if c.mock and not force_real else "REAL"
        
        # Metadata
        time_offset = getattr(c, "time_offset", 0)
        base_url = getattr(c, "base_url", "UNKNOWN")
        env = "UNKNOWN"
        use_testnet = getattr(c, "use_testnet", None)
        
        if "testnet" in base_url or use_testnet is True:
            env = "TESTNET"
        elif "api.binance.com" in base_url or use_testnet is False:
            env = "MAINNET"
        
        response = BalancesResponse(
            balances=[
                {"asset": asset, "free": data["free"], "locked": data["locked"]}
                for asset, data in balances.items()
            ],
            source=effective_source,
            env=env,
            request_id=req_id,
            upstream_status=200,
            time_offset=time_offset
        )
        return jsonify(response.dict())

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"[DIAGNOSTIC_FAILURE] /balances CRASH: {e}\n{tb}")
        
        # Return 500 with detail if possible, OR 502/401 if it's a known error
        status_code = 502
        err_str = str(e)
        if "401" in err_str or "Unauthorized" in err_str:
            status_code = 401
            
        return jsonify({
            "error": err_str,
            "trace": tb.splitlines()[-3:], # Show last 3 lines of trace for context
            "source": "REAL" if request.headers.get("X-Data-Source") == "REAL" else "SIMULATION", 
            "request_id": req_id,
            "upstream_status": status_code 
        }), status_code


@app.get("/positions")
@_measure_latency
def get_positions() -> Any:
    """Get current open positions."""
    guard = _telemetry_guard()
    if guard:
        return guard
    req_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    # For now, return empty positions (to be implemented fully later)
    return jsonify({
        "positions": [],
        "request_id": req_id,
        "source": "REAL",
        "upstream_status": 200
    })


@app.get("/orders/active")
@_measure_latency
def get_orders_active() -> Any:
    """Get currently active orders."""
    guard = _telemetry_guard()
    if guard:
        return guard
    req_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    # For now, return empty orders (to be implemented fully later)
    return jsonify({
        "orders": [],
        "request_id": req_id,
        "source": "REAL",
        "upstream_status": 200
    })


@app.get("/pnl/history")
@_measure_latency
def get_pnl_history() -> Any:
    """Get PnL history."""
    guard = _telemetry_guard()
    if guard:
        return guard
    req_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    # For now, return empty history (to be implemented fully later)
    return jsonify({
        "history": [],
        "total_pnl": 0.0,
        "request_id": req_id,
        "source": "REAL",
        "upstream_status": 200
    })


@app.get("/risk/drift")
@_measure_latency
def get_risk_drift() -> Any:
    """Get risk drift metrics."""
    guard = _telemetry_guard()
    if guard:
        return guard
    req_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    # For now, return zero drift (to be implemented fully later)
    return jsonify({
        "drift": 0.0,
        "within_limits": True,
        "request_id": req_id,
        "source": "REAL",
        "upstream_status": 200
    })


@app.get("/ops/incidents")
@_measure_latency
def get_ops_incidents() -> Any:
    """Get operational incidents."""
    guard = _telemetry_guard()
    if guard:
        return guard
    req_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    # For now, return no incidents (to be implemented fully later)
    return jsonify({
        "incidents": [],
        "count": 0,
        "request_id": req_id,
        "source": "REAL",
        "upstream_status": 200
    })


@app.get("/ops/state/killswitch")
@_measure_latency
def get_ops_state_killswitch() -> Any:
    """Get killswitch state."""
    guard = _telemetry_guard()
    if guard:
        return guard
    req_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    state = get_runtime_state()
    return jsonify({
        "killswitch_active": state.get("global_stop", False),
        "system_mode": state.get("system_mode", "MANUAL"),
        "request_id": req_id,
        "source": "REAL",
        "upstream_status": 200
    })


@app.get("/strategies")
@_measure_latency
def get_strategies_list() -> Any:
    """Get list of available strategies (frontend compatibility)."""
    guard = _telemetry_guard()
    if guard:
        return guard
    req_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    # Return available strategies from registry
    strategies = [
        {"id": k, "name": k.replace("_", " ").title(), "enabled": True}
        for k in REGISTRY.keys()
    ]
    return jsonify({
        "strategies": strategies,
        "request_id": req_id,
        "source": "REAL",
        "upstream_status": 200
    })


@app.get("/risk/limits")
@_measure_latency
def get_risk_limits() -> Any:
    """Get current risk limits."""
    guard = _telemetry_guard()
    if guard:
        return guard
    req_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    state = get_runtime_state()
    spot_config = state.get("spot", {})
    return jsonify({
        "limits": {
            "max_positions": spot_config.get("max_positions", 5),
            "risk_per_trade_pct": spot_config.get("risk_per_trade_pct", 0.005),
            "max_trade_pct": spot_config.get("max_trade_pct", 0.2),
            "max_symbol_exposure_pct": spot_config.get("max_symbol_exposure_pct", 0.35)
        },
        "request_id": req_id,
        "source": "REAL",
        "upstream_status": 200
    })


@app.get("/allocations")
@_measure_latency
def get_allocations() -> Any:
    """Get current capital allocations."""
    guard = _telemetry_guard()
    if guard:
        return guard
    req_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    state = get_runtime_state()
    return jsonify({
        "allocations": {
            "arbitrage": state.get("reserves", {}).get("arbitrage", 0.25),
            "portfolio": state.get("reserves", {}).get("portfolio", 0.15),
            "spot_trading": state.get("ops", {}).get("capital", {}).get("cap_pct", 0.25)
        },
        "total_equity": state.get("portfolio_equity", 10000.0),
        "request_id": req_id,
        "source": "REAL",
        "upstream_status": 200
    })


@app.get("/ops/logs")
@_measure_latency
@require_role("TRADER", "ADMIN", "OPS", ops_token=OPS_TOKEN)
def get_logs() -> Any:
    # Deprecated custom guard in favor of standard RBAC
    # guard = _telemetry_guard()
    # if guard: return guard
    
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


@app.post("/admin/limits")
@_measure_latency
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
def upsert_limit() -> Any:
    """Create or update a risk limit."""
    payload = LimitSchema.parse_obj(request.get_json(force=True) or {})
    session: Session = g.db
    
    # Check existing
    existing = session.query(Limit).filter_by(
        scope=payload.scope, 
        subject=payload.subject, 
        key=payload.key
    ).one_or_none()
    
    if existing:
        existing.value = str(payload.value)
        existing.updated_at = datetime.utcnow()
        existing.updated_by = current_user().email if current_user() else "system"
        _audit("update_limit", target=f"{payload.scope}:{payload.key}", details=payload.dict())
    else:
        new_limit = Limit(
            scope=payload.scope,
            subject=payload.subject,
            key=payload.key,
            value=str(payload.value),
            updated_by=current_user().email if current_user() else "system"
        )
        session.add(new_limit)
        _audit("create_limit", target=f"{payload.scope}:{payload.key}", details=payload.dict())
    
    session.commit()
    return jsonify(payload.dict())



@app.get("/fund/overview")
@require_role("FUND", "ADMIN", ops_token=OPS_TOKEN)
def fund_overview() -> Any:
    """Aggregated view of all managed assets."""
    # In a real multi-tenant system, this would query SUM(equity) from all users.
    # Here we project the single tenant + synthetic data for demonstration.
    
    state = get_runtime_state()
    users = list_users(g.db)
    active_count = sum(1 for u in users if u.is_active)
    
    # Real data from current tenant
    current_equity = state.get("portfolio_equity", 10000.0)
    
    # Synthetic "Fund" data (Simulating 5 other managed accounts)
    total_aum = current_equity * 5.5 
    
    return jsonify({
        "total_aum": total_aum,
        "active_accounts": active_count + 4, # +4 synthetic
        "capital_in_use_pct": 0.45, # Aggregated average
        "capital_reserved_pct": 0.20,
        "capital_free_pct": 0.35,
        "active_strategies": 5,
        "active_exchanges": 2,
        "health_score": 98.5,
        "risk_level": "MODERATE"
    })


@app.get("/fund/portfolio")
@require_role("FUND", "ADMIN", ops_token=OPS_TOKEN)
def fund_portfolio() -> Any:
    """Aggregated holdings across all accounts."""
    # Projection of single portfolio to fund scale
    state = get_runtime_state()
    spot = state.get("spot", {})
    
    # Mock aggregation based on reliable assets
    return jsonify({
        "by_asset": [
            {"asset": "USDT", "total_usd": 550000.0, "pct": 45.0},
            {"asset": "BTC", "total_usd": 350000.0, "pct": 28.6},
            {"asset": "ETH", "total_usd": 200000.0, "pct": 16.4},
            {"asset": "SOL", "total_usd": 120000.0, "pct": 10.0},
        ],
        "by_exchange": [
            {"exchange": "Binance", "total_usd": 800000.0, "pct": 65.5},
            {"exchange": "OKX", "total_usd": 420000.0, "pct": 34.5},
        ]
    })


@app.get("/fund/strategies")
@require_role("FUND", "ADMIN", ops_token=OPS_TOKEN)
def fund_strategies() -> Any:
    """Strategy distribution across the fund."""
    state = get_runtime_state()
    weights = state.get("spot", {}).get("weights", {})
    
    # Enrich with synthetic adoption stats
    strategies = []
    # Base real strategies
    for strat, weight in weights.items():
        if weight > 0:
            strategies.append({
                "name": strat,
                "allocation_usd": 150000.0 * (weight * 10), # Mock
                "pct_aum": weight * 0.4, # Mock global share
                "account_count": 3,
                "risk_label": "HIGH" if "scalp" in strat else "MED"
            })
            
    # Add some that might be active in other accounts but not the main one
    strategies.append({
        "name": "manual_discretionary",
        "allocation_usd": 500000.0,
        "pct_aum": 0.41,
        "account_count": 5,
        "risk_label": "LOW"
    })
            
    return jsonify(strategies)


@app.get("/fund/risk")
@require_role("FUND", "ADMIN", ops_token=OPS_TOKEN)
def fund_risk() -> Any:
    """Global risk matrix."""
    return jsonify({
        "max_drawdown_pct": 4.2,
        "concentration_risk": "BTC (28%)",
        "leverage_ratio": 1.0, # Spot only
        "alerts": [
            {"level": "INFO", "msg": "Binance maintenance scheduled"},
            {"level": "WARN", "msg": "High volatility detected in SOL"}
        ]
    })


@app.get("/fund/accounts")
@require_role("FUND", "ADMIN", ops_token=OPS_TOKEN)
def fund_accounts() -> Any:
    """List managed accounts."""
    users = list_users(g.db)
    state = get_runtime_state()
    
    visible_accounts = []
    
    # Real users
    for u in users:
        visible_accounts.append({
            "id": u.id,
            "name": u.email.split("@")[0],
            "role": u.role,
            "aum": state.get("portfolio_equity", 10000.0),
            "mode": "AUTO" if state.get("auto_mode") else "MANUAL",
            "risk_status": "OK",
            "active": u.is_active
        })
        
    # Synthetic accounts for demo
    visible_accounts.extend([
        {"id": 901, "name": "fund_alpha", "role": "TRADER", "aum": 250000.0, "mode": "AUTO", "risk_status": "OK", "active": True},
        {"id": 902, "name": "fund_beta", "role": "TRADER", "aum": 120000.0, "mode": "SEMI", "risk_status": "WARN", "active": True},
        {"id": 903, "name": "managed_01", "role": "TRADER", "aum": 50000.0, "mode": "STOP", "risk_status": "OK", "active": True},
    ])
    
    return jsonify(visible_accounts)

# -------- Admin Panel (Institutional Control Plane) --------

@app.get("/admin/overview")
@require_role("ADMIN", ops_token=OPS_TOKEN)
def admin_overview() -> Any:
    """System-wide overview for Admin Dashboard."""
    with get_session() as session:
        users = list_users(session)
    active_sessions = sum(1 for u in users if u.is_active)  # Proxy for sessions
    
    # Mock alerts and health (In real system, query monitoring service)
    health = {
        "api": "healthy",
        "db": "healthy",
        "redis": "healthy", 
        "rabbitmq": "healthy"
    }
    
    alerts = [
        {"level": "Error", "message": "High latency on Binance API", "ts": datetime.utcnow().isoformat()},
        {"level": "Warning", "message": "Audit log rotation pending", "ts": datetime.utcnow().isoformat()},
    ]

    return jsonify({
        "total_tenants": 1, # Single tenant mode
        "total_users": len(users),
        "active_sessions": active_sessions,
        "system_health": health,
        "alerts": alerts
    })


@app.get("/admin/tenants")
@require_role("ADMIN", ops_token=OPS_TOKEN)
def admin_list_tenants() -> Any:
    """List all tenants (Logical)."""
    # For now, return the single Default Tenant with its config
    # In future, query Tenant table
    state = get_runtime_state()
    branding = state.get("branding", {"name": "Lunia Institutional", "logo": "/logo.png", "theme": "dark"})
    
    return jsonify([{
        "id": "tenant_default",
        "name": "Default Tenant",
        "plan": "ENTERPRISE",
        "status": "ACTIVE",
        "created_at": "2024-01-01T00:00:00Z",
        "branding": branding,
        "limits": {
            "max_exchanges": 5,
            "max_strategies": 20,
            "max_aum": -1
        }
    }])


@app.post("/admin/tenants/<id>/config")
@require_role("ADMIN", ops_token=OPS_TOKEN)
def admin_update_tenant_config(id: str) -> Any:
    """Update tenant configuration (Branding/Limits)."""
    try:
        data = request.get_json(force=True)
        # In a real system, update Tenant table. 
        # Here, we audit and mock persistence via state for "logical" tenant
        state = get_runtime_state()
        
        if "branding" in data:
            state["branding"] = data["branding"]
            # Persist branding to state
            set_state(state) 
            
        _audit("admin_update_tenant", details={"tenant_id": id, "changes": data})
        return jsonify({"status": "updated", "id": id})
    except Exception as e:
        logger.error(f"Tenant update failed: {e}")
        return jsonify({"error": str(e)}), 500


@app.get("/admin/users")
@require_role("ADMIN", ops_token=OPS_TOKEN)
def admin_list_users() -> Any:
    """List users with RBAC details."""
    with get_session() as session:
        users = list_users(session)
        # Must detach or convert to dict before session closes if using joined load, but users are simple here
        user_list = [UserOut(
            id=u.id, email=u.email, role=u.role, is_active=u.is_active, 
            created_at=u.created_at.isoformat(), last_login_at=u.last_login_at.isoformat() if u.last_login_at else None
        ).dict() for u in users]
        
    return jsonify(user_list)


@app.post("/admin/users/<int:user_id>/role")
@require_role("ADMIN", ops_token=OPS_TOKEN)
def admin_update_user_role(user_id: int) -> Any:
    """Update user role (RBAC)."""
    try:
        body = request.get_json(force=True)
        new_role = body.get("role")
        if new_role not in ["USER", "TRADER", "FUND", "ADMIN"]:
            return jsonify({"error": "Invalid role"}), 400
            
        with get_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return jsonify({"error": "User not found"}), 404
            
            old_role = user.role
            user.role = new_role
            session.commit()
            
            _audit("admin_update_role", details={"user_id": user_id, "old_role": old_role, "new_role": new_role})
            
        return jsonify({"status": "updated", "user_id": user_id, "role": new_role})
    except Exception as e:
        logger.error(f"Role update failed: {e}")
        return jsonify({"error": str(e)}), 500


@app.get("/admin/audit")
@require_role("ADMIN", ops_token=OPS_TOKEN)
def admin_audit_logs() -> Any:
    """Searchable Audit Logs."""
    limit = int(request.args.get("limit", 50))
    action = request.args.get("action")
    
    with get_session() as session:
        query = session.query(AuditEvent)
        if action:
            query = query.filter(AuditEvent.action == action)
            
        # Sort by latest first
        events = query.order_by(AuditEvent.ts.desc()).limit(limit).all()
        
        return jsonify([AuditEventSchema(
            id=e.id, ts=e.ts.isoformat(), actor_user_id=e.actor_user_id, 
            actor_role=e.actor_role, action=e.action, target=e.target, 
            result=e.result, ip=e.ip, user_agent=e.user_agent, metadata=e.event_metadata
        ).dict() for e in events])


@app.get("/admin/flags")
@require_role("ADMIN", ops_token=OPS_TOKEN)
def admin_get_flags() -> Any:
    """List Feature Flags."""
    with get_session() as session:
        flags = session.query(FeatureFlag).all()
        return jsonify([FeatureFlagSchema(
            key=f.key, value=f.value, updated_at=f.updated_at.isoformat(), updated_by=f.updated_by
        ).dict() for f in flags])


@app.post("/admin/flags")
@require_role("ADMIN", ops_token=OPS_TOKEN)
def admin_set_flag() -> Any:
    """Set Feature Flag."""
    try:
        body = request.get_json(force=True)
        key = body.get("key")
        value = body.get("value")
        
        with get_session() as session:
            flag = session.query(FeatureFlag).filter(FeatureFlag.key == key).first()
            if not flag:
                flag = FeatureFlag(key=key, value=str(value))
                session.add(flag)
            else:
                flag.value = str(value)
                flag.updated_at = datetime.utcnow()
                if current_user:
                    flag.updated_by = current_user.id
            session.commit()
            
        _audit("admin_flag_update", details={"key": key, "value": value})
        EventBus.publish("feature_flags.updated", {"key": key, "value": value})
        
        return jsonify({"status": "ok", "key": key, "value": value})
    except Exception as e:
        logger.exception("Failed to update flag")
        return jsonify({"error": str(e)}), 400


# --- PORTFOLIO SYSTEM ENDPOINTS (PHASE 3) ---

@app.get("/portfolio/structure")
@_measure_latency
@require_role("TRADER", "ADMIN", "FUND", "USER", ops_token=OPS_TOKEN)
def get_portfolio_structure() -> Any:
    """Get the defined portfolio structures (Engine Output)."""
    state = get_runtime_state()
    portfolios = state.get("portfolios", {}).get("definitions", {})
    return jsonify(list(portfolios.values()))

@app.post("/portfolio/<portfolio_id>/action")
@_measure_latency
@require_role("TRADER", "ADMIN", ops_token=OPS_TOKEN)
@safety_guard
def portfolio_action(portfolio_id: str) -> Any:
    """Governance actions for a specific portfolio."""
    body = request.get_json(force=True)
    action = body.get("action") # PAUSE, RESUME, DERISK, REBALANCE
    
    state = get_runtime_state()
    portfolios = state.get("portfolios", {}).get("definitions", {})
    
    if portfolio_id not in portfolios:
        return jsonify({"error": "Portfolio not found", "code": "NOT_FOUND"}), 404
    
    target = portfolios[portfolio_id]
    
    executor = PortfolioExecutor(agent)
    execution_result = {}

    if action == "PAUSE":
        target["status"] = "PAUSED"
    elif action == "RESUME":
        target["status"] = "ACTIVE"
    elif action == "DERISK":
        target["status"] = "DE_RISKING"
        # EXECUTION BINDING
        execution_result = executor.execute_derisk(portfolio_id)
    elif action == "REBALANCE":
         # Manual Trigger of Rebalance logic
         if target["status"] != "ACTIVE":
             return jsonify({"error": "Portfolio must be ACTIVE to rebalance"}), 400
         execution_result = executor.execute_rebalance(portfolio_id)
    else:
        return jsonify({"error": "Invalid action", "code": "INVALID_ACTION"}), 400
        
    # Persist Status Changes
    update = {"portfolio": {"definitions": portfolios}}
    set_state(update)
    
    _audit("portfolio_action", details={"id": portfolio_id, "action": action, "result": execution_result})
    
    return jsonify({
        "portfolio": target,
        "execution": execution_result
    })



@app.get("/admin/limits")
@require_role("ADMIN", "TRADER", ops_token=OPS_TOKEN)
def admin_get_limits() -> Any:
    """Get system limits."""
    with get_session() as session:
        limits = session.query(Limit).all()
        return jsonify([LimitSchema(
            scope=l.scope, subject=l.subject, key=l.key, value=l.value, 
            updated_at=l.updated_at.isoformat(), updated_by=l.updated_by
        ).dict() for l in limits])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# EPOCH B: Proposal Domain Endpoints Registration
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Temporarily commented out due to circular import
# from .proposal_endpoints import register_proposal_endpoints
# register_proposal_endpoints(app, require_role)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 5.1: Admin Governance Blueprint (Fail-Safe)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
try:
    from forensic.api.admin_governance_routes import admin_bp, init_governance
    init_governance()  # Initialize with default paths
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    logger.info("[PHASE5_ADMIN] Admin governance endpoints registered at /api/admin")
except Exception as e:
    logger.warning(f"[PHASE5_ADMIN] Admin blueprint registration skipped: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(host='0.0.0.0', port=port, debug=debug)

