"""Runtime utilities for the arbitrage service."""
from __future__ import annotations

import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional

from app.core.bus import get_bus
from app.core.exchange.binance_spot import BinanceSpot
from app.core.exchange.bybit_spot import BybitSpot
from app.core.exchange.okx_spot import OKXSpot
from app.core.metrics import (
    arb_auto_execs_total,
    arb_daily_pnl_usd,
    arb_net_profit_total_usd,
    arb_success_rate,
    ensure_metrics_server,
)
from app.core.portfolio.portfolio import Portfolio
from app.core.risk.manager import RiskManager
from app.core.risk.rate_limit import RateLimiter
from app.core.state import get_state as get_runtime_state, set_state
from app.db.reporting import arbitrage_daily_pnl
from app.services.guard.alerts import evaluate_and_alert
from app.services.reports.exporter import get_exporter
from app.db.reporting import arbitrage_daily_summary

from .auto_manager import ArbitrageAutoManager
from .executor_safe import ArbitrageExecutionResult, SafeArbitrageExecutor
from .scanner import ArbitrageFilters, ArbitrageOpportunity, ArbitrageScanner
from .strategy import ArbitrageStrategy

logger = logging.getLogger(__name__)


@dataclass
class RuntimeSnapshot:
    total_scans: int = 0
    last_scan_ts: float = 0.0
    last_latency_ms: float = 0.0
    last_opportunities: List[Dict[str, object]] = field(default_factory=list)
    last_objects: List[ArbitrageOpportunity] = field(default_factory=list)
    history: Deque[Dict[str, object]] = field(default_factory=lambda: deque(maxlen=50))
    executions: Dict[str, Dict[str, object]] = field(default_factory=dict)
    last_execution: Optional[Dict[str, object]] = None
    total_executions: int = 0
    total_pnl: float = 0.0
    last_decision: str = ""
    success_count: int = 0
    fail_count: int = 0

    def snapshot(self) -> Dict[str, object]:
        return {
            "total_scans": self.total_scans,
            "last_scan_ts": self.last_scan_ts,
            "last_latency_ms": self.last_latency_ms,
            "total_opportunities": len(self.last_opportunities),
            "total_executions": self.total_executions,
            "last_execution": self.last_execution,
            "total_pnl": self.total_pnl,
            "last_decision": self.last_decision,
        }

    def recent(self, limit: int) -> List[Dict[str, object]]:
        items = list(self.history)
        if not items:
            return []
        limit = max(1, min(limit, len(items)))
        return items[-limit:]

    def register_execution(self, result: ArbitrageExecutionResult, auto_trigger: bool) -> None:
        payload = result.to_dict()
        self.executions[result.exec_id] = payload
        self.last_execution = payload
        self.total_executions += 1
        self.total_pnl = payload.get("pnl_usd", 0.0) + self.total_pnl
        arb_net_profit_total_usd.set(self.total_pnl)
        if auto_trigger:
            arb_auto_execs_total.labels(mode=result.mode).inc()
        if payload.get("status") == "FILLED":
            self.success_count += 1
        else:
            self.fail_count += 1
        total_attempts = max(1, self.success_count + self.fail_count)
        arb_success_rate.set(self.success_count / total_attempts)
        arb_daily_pnl_usd.set(arbitrage_daily_pnl())
        evaluate_and_alert(arbitrage_daily_summary())

    def get_execution(self, exec_id: str) -> Optional[Dict[str, object]]:
        return self.executions.get(exec_id)

    def register_failure(self) -> None:
        self.fail_count += 1
        total_attempts = max(1, self.success_count + self.fail_count)
        arb_success_rate.set(self.success_count / total_attempts)
        arb_daily_pnl_usd.set(arbitrage_daily_pnl())
        evaluate_and_alert(arbitrage_daily_summary())


_RUNTIME = RuntimeSnapshot()
_SCANNER: ArbitrageScanner | None = None
_EXECUTOR: SafeArbitrageExecutor | None = None
_STRATEGY = ArbitrageStrategy()
_AUTO_MANAGER: ArbitrageAutoManager | None = None


def _init_components() -> None:
    global _SCANNER, _EXECUTOR, _AUTO_MANAGER
    if _SCANNER is None:
        exchanges = {
            "binance": BinanceSpot(),
            "okx": OKXSpot(),
            "bybit": BybitSpot(),
        }
        state = get_runtime_state()
        qty_usd = float(state.get("arb", {}).get("qty_usd", 100.0))
        symbols = ["BTCUSDT", "ETHUSDT"]
        _SCANNER = ArbitrageScanner(exchanges=exchanges, symbols=symbols, qty_usd=qty_usd)
    if _EXECUTOR is None:
        _EXECUTOR = SafeArbitrageExecutor(
            portfolio=Portfolio(),
            risk=RiskManager(),
            rate_limiter=RateLimiter(),
        )
    if _AUTO_MANAGER is None:
        _AUTO_MANAGER = ArbitrageAutoManager(_scan_for_auto, _execute_for_auto)
    ensure_metrics_server(9102)


def _build_filters() -> ArbitrageFilters:
    state = get_runtime_state()
    arb_state = state.get("arb", {})
    filters = arb_state.get("filters", {})
    return ArbitrageFilters(
        min_net_roi_pct=float(filters.get("min_net_roi_pct", 0.0)),
        max_net_roi_pct=float(filters.get("max_net_roi_pct", 100.0)),
        min_net_usd=float(filters.get("min_net_usd", 0.0)),
        top_k=int(filters.get("top_k", 5)),
        sort_key=str(filters.get("sort_key", "net_roi_pct")),
        sort_dir=str(filters.get("sort_dir", "desc")),
    )


def scan_now() -> List[Dict[str, object]]:
    _init_components()
    assert _SCANNER is not None
    filters = _build_filters()
    start = time.time()
    opportunities = _SCANNER.scan(filters)
    latency_ms = (time.time() - start) * 1000
    serialized = [opp.to_dict() for opp in opportunities]
    _RUNTIME.total_scans += 1
    _RUNTIME.last_scan_ts = time.time()
    _RUNTIME.last_latency_ms = latency_ms
    _RUNTIME.last_opportunities = serialized
    _RUNTIME.last_objects = opportunities
    exporter = get_exporter()
    if exporter:
        try:
            exporter.export_if_due()
        except Exception as exc:  # pragma: no cover - export failures
            logger.warning("export failed: %s", exc)
    for payload in serialized:
        _RUNTIME.history.append(payload)
        bus = get_bus()
        if bus:
            try:
                bus.publish("arbitrage", payload)
            except Exception as exc:  # pragma: no cover
                logger.warning("Failed to publish arbitrage payload: %s", exc)
    logger.info("scan complete count=%s latency_ms=%.2f", len(serialized), latency_ms)
    return serialized


def _scan_for_auto(filters: ArbitrageFilters) -> List[ArbitrageOpportunity]:
    _init_components()
    assert _SCANNER is not None
    opportunities = _SCANNER.scan(filters)
    exporter = get_exporter()
    if exporter:
        try:
            exporter.export_if_due()
        except Exception as exc:  # pragma: no cover - export failures
            logger.warning("export failed: %s", exc)
    return opportunities


def _execute_for_auto(opportunity: ArbitrageOpportunity) -> None:
    _RUNTIME.last_decision = "auto_execute"
    execute_opportunity(opportunity, auto_trigger=True)


def execute_opportunity(
    opportunity: ArbitrageOpportunity,
    *,
    mode: Optional[str] = None,
    transfer: str = "auto",
    pin: Optional[str] = None,
    double_confirm: bool = False,
    auto_trigger: bool = False,
) -> Dict[str, object]:
    _init_components()
    assert _EXECUTOR is not None
    try:
        result = _EXECUTOR.execute(
            opportunity,
            mode=mode,
            transfer_preference=transfer,
            pin=pin,
            double_confirm=double_confirm,
            auto_trigger=auto_trigger,
        )
    except Exception:
        _RUNTIME.register_failure()
        raise
    _RUNTIME.register_execution(result, auto_trigger)
    bus = get_bus()
    if bus:
        try:
            bus.publish("arbitrage.exec", result.to_dict())
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to publish arbitrage exec: %s", exc)
    return result.to_dict()


def execute_by_id(
    proposal_id: str,
    *,
    mode: Optional[str] = None,
    transfer: str = "auto",
    pin: Optional[str] = None,
    double_confirm: bool = False,
) -> Dict[str, object]:
    _init_components()
    assert _SCANNER is not None
    current = next((opp for opp in _SCANNER.last_opportunities if opp.proposal_id == proposal_id), None)
    if current is None:
        raise ValueError("proposal not found in recent scan")
    return execute_opportunity(
        current,
        mode=mode,
        transfer=transfer,
        pin=pin,
        double_confirm=double_confirm,
    )


def update_filters(payload: Dict[str, object]) -> Dict[str, object]:
    set_state({"arb": {"filters": payload}})
    return get_runtime_state()


def toggle_auto_mode(enabled: bool) -> Dict[str, object]:
    set_state({"arb": {"auto_mode": enabled}})
    return get_runtime_state()


def get_state() -> RuntimeSnapshot:
    return _RUNTIME


def get_filters() -> ArbitrageFilters:
    return _build_filters()


def get_execution(exec_id: str) -> Optional[Dict[str, object]]:
    return _RUNTIME.get_execution(exec_id)


def run_worker() -> None:  # pragma: no cover - long running loop
    interval = int(os.getenv("ARB_SCAN_INTERVAL", "60"))
    _init_components()
    while True:
        filters = _build_filters()
        scan_now()
        if _AUTO_MANAGER is not None:
            outcome = _AUTO_MANAGER.maybe_run(filters)
            _RUNTIME.last_decision = outcome.decision.reason
        time.sleep(max(5, interval))


def auto_tick() -> str:
    _init_components()
    if _AUTO_MANAGER is None:
        return "auto_manager_missing"
    filters = _build_filters()
    outcome = _AUTO_MANAGER.maybe_run(filters)
    _RUNTIME.last_decision = outcome.decision.reason
    return outcome.decision.reason


__all__ = [
    "scan_now",
    "execute_opportunity",
    "execute_by_id",
    "update_filters",
    "toggle_auto_mode",
    "get_state",
    "get_filters",
    "get_execution",
    "auto_tick",
    "run_worker",
]
