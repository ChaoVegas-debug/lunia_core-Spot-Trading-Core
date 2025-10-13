"""Flask API exposing Lunia core functionality."""
from __future__ import annotations

import logging
import os
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List

from app.compat.dotenv import load_dotenv
from flask import Flask, Response, jsonify, request
from pydantic import ValidationError

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
from ..ai_research import run_research_now
from ..arbitrage import bp as arbitrage_bp
from ..arbitrage.worker import get_state as get_arbitrage_state
from ..api.schemas import (
    ArbitrageOpportunities,
    BalancesResponse,
    CapitalRequest,
    FuturesTradeRequest,
    OpsState,
    OpsStateUpdate,
    PortfolioPosition,
    PortfolioSnapshot,
    ReserveUpdateRequest,
    ResearchRequest,
    ResearchResponse,
    SignalPayload,
    SignalsEnvelope,
    SpotRiskUpdate,
    StrategyWeightsRequest,
    TradeRequest,
)

load_dotenv()

LOG_DIR = Path(__file__).resolve().parents[4] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
API_LOG_PATH = LOG_DIR / "api.log"
OPS_TOKEN = os.getenv("OPS_API_TOKEN")

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.FileHandler(API_LOG_PATH, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

START_TIME = time.time()


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


def _ensure_admin_request() -> bool:
    if OPS_TOKEN is None:
        return True
    header = request.headers.get("X-Admin-Token")
    if header != OPS_TOKEN:
        logger.warning("Forbidden ops request")
        return False
    return True


@app.get("/health")
@_measure_latency
def health() -> Any:
    logger.info("/health requested")
    return jsonify({"status": "ok"})


@app.get("/cores")
@_measure_latency
def cores() -> Any:
    logger.info("/cores requested")
    return jsonify(CORES)


@app.get("/status")
@_measure_latency
def status() -> Any:
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


@app.get("/ops/state")
@_measure_latency
def ops_state() -> Any:
    logger.info("/ops/state requested")
    state = OpsState.parse_obj(get_runtime_state())
    return jsonify(state.dict())


@app.post("/ops/state")
@_measure_latency
def ops_state_update() -> Any:
    if not _ensure_admin_request():
        return jsonify({"error": "forbidden"}), 403
    payload = OpsStateUpdate.parse_obj(request.get_json(force=True) or {})
    filtered = {k: v for k, v in payload.dict().items() if v is not None}
    state = set_state(filtered)
    logger.info("Ops state updated: %s", filtered)
    return jsonify(OpsState.parse_obj(state).dict())


def _ops_toggle(key: str, value: bool) -> Any:
    if not _ensure_admin_request():
        return jsonify({"error": "forbidden"}), 403
    state = set_state({key: value})
    return jsonify(OpsState.parse_obj(state).dict())


@app.post("/ops/auto_on")
def ops_auto_on() -> Any:
    return _ops_toggle("auto_mode", True)


@app.post("/ops/auto_off")
def ops_auto_off() -> Any:
    return _ops_toggle("auto_mode", False)


@app.post("/ops/stop_all")
def ops_stop_all() -> Any:
    return _ops_toggle("global_stop", True)


@app.post("/ops/start_all")
def ops_start_all() -> Any:
    return _ops_toggle("global_stop", False)


@app.get("/ops/equity")
@_measure_latency
def ops_equity() -> Any:
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
def ops_capital_update() -> Any:
    if not _ensure_admin_request():
        return jsonify({"error": "forbidden"}), 403
    payload = CapitalRequest.parse_obj(request.get_json(force=True) or {})
    state = set_state({"ops": {"capital": {"cap_pct": payload.cap_pct}}})
    snapshot = _capital_snapshot()
    response = {
        "state": OpsState.parse_obj(state).dict(),
        "cap_pct": snapshot["cap_pct"],
        "tradable_equity_usd": snapshot["allocation"].tradable_equity,
    }
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
def spot_alloc_update() -> Any:
    if not _ensure_admin_request():
        return jsonify({"error": "forbidden"}), 403
    payload = ReserveUpdateRequest.parse_obj(request.get_json(force=True) or {})
    update: Dict[str, Any] = {"reserves": {}}
    if payload.portfolio is not None:
        update["reserves"]["portfolio"] = payload.portfolio
    if payload.arbitrage is not None:
        update["reserves"]["arbitrage"] = payload.arbitrage
    state = set_state(update)
    return jsonify(OpsState.parse_obj(state).dict())


@app.get("/spot/risk")
@_measure_latency
def spot_risk() -> Any:
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
def spot_risk_update() -> Any:
    if not _ensure_admin_request():
        return jsonify({"error": "forbidden"}), 403
    payload = SpotRiskUpdate.parse_obj(request.get_json(force=True) or {})
    update = {"spot": {k: v for k, v in payload.dict(exclude_none=True).items()}}
    state = set_state(update)
    return jsonify(OpsState.parse_obj(state).dict())


@app.post("/spot/backtest")
@_measure_latency
def spot_backtest() -> Any:
    if not _ensure_admin_request():
        return jsonify({"error": "forbidden"}), 403
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
    return jsonify(result), status_code


@app.post("/trade/futures/demo")
@_measure_latency
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
    return jsonify({"ok": True, "order": order})


@app.post("/ai/research/analyze_now")
@_measure_latency
def ai_research_analyze_now() -> Any:
    if not _ensure_admin_request():
        return jsonify({"error": "forbidden"}), 403
    logger.info("/ai/research/analyze_now invoked")
    payload = request.get_json(silent=True) or {}
    req = ResearchRequest.parse_obj(payload)
    results = run_research_now(req.pairs, mode="manual")
    return jsonify(ResearchResponse(results=results).dict())


def _publish_signals(signals: Iterable[SignalPayload]) -> None:
    for signal in signals:
        supervisor.bus.publish(
            "signals",
            {"symbol": signal.symbol, "side": signal.side, "qty": signal.qty},
        )


@app.post("/ai/run")
@_measure_latency
def run_ai() -> Any:
    logger.info("/ai/run invoked")
    decision = supervisor.get_signals()
    payload = SignalsEnvelope.parse_obj(decision)
    _publish_signals(payload.signals)
    results = agent.execute_signals(decision)
    logger.info("/ai/run completed executed=%s errors=%s", results["executed"], results["errors"])
    return jsonify(results)


@app.post("/signal")
@_measure_latency
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
    return jsonify(results)


@app.get("/arbitrage/opps")
@_measure_latency
def get_arbitrage_opportunities() -> Any:
    state = get_arbitrage_state()
    return jsonify(ArbitrageOpportunities(opportunities=state.recent(10)).dict())


@app.get("/portfolio")
@_measure_latency
def get_portfolio() -> Any:
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


@app.get("/balances")
@_measure_latency
def get_balances() -> Any:
    logger.info("/balances requested")
    balances = agent.client.get_balances()
    response = BalancesResponse(
        balances=[
            {"asset": asset, "free": data["free"], "locked": data["locked"]}
            for asset, data in balances.items()
        ]
    )
    return jsonify(response.dict())


@app.get("/metrics")
def metrics_endpoint() -> Response:
    return Response(scrape_metrics(), mimetype="text/plain")


if __name__ == "__main__":  # pragma: no cover
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    app.run(host=host, port=port)
