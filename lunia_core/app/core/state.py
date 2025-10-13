"""Global runtime state management for Lunia core."""
from __future__ import annotations

import json
import logging
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

from app.compat.dotenv import load_dotenv

from .metrics import (
    arb_filter_changes_total,
    ops_auto_mode,
    ops_global_stop,
    ops_state_changes_total,
)

load_dotenv()

LOG_DIR = Path(__file__).resolve().parents[4] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
STATE_PATH = LOG_DIR / "state.json"
STATE_LOG = LOG_DIR / "state.log"

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.FileHandler(STATE_LOG, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


_DEFAULT_SCALP = {
    "tp_pct": float(os.getenv("SCALP_TP_PCT", "0.30")),
    "sl_pct": float(os.getenv("SCALP_SL_PCT", "0.15")),
    "qty_usd": float(os.getenv("SCALP_QTY_USD", "100")),
}

_ARB_SORT_KEYS = {"net_roi_pct", "net_profit_usd"}
_ARB_SORT_DIRS = {"asc", "desc"}

_DEFAULT_ARB = {
    "interval": int(os.getenv("ARB_SCAN_INTERVAL", "60")),
    "threshold_pct": float(os.getenv("ARB_SPREAD_THRESHOLD_PCT", "0.25")),
    "qty_usd": float(os.getenv("ARB_QTY_USD", "100")),
    "qty_min_usd": float(os.getenv("ARB_QTY_MIN_USD", os.getenv("ARB_QTY_USD", "100"))),
    "qty_max_usd": float(os.getenv("ARB_QTY_MAX_USD", os.getenv("ARB_QTY_USD", "100"))),
    "auto_mode": os.getenv("ARB_AUTO_MODE", "false").lower() == "true",
    "filters": {
        "min_net_roi_pct": float(os.getenv("ARB_MIN_NET_ROI_PCT", "1.0")),
        "max_net_roi_pct": float(os.getenv("ARB_MAX_NET_ROI_PCT", "100.0")),
        "min_net_usd": float(os.getenv("ARB_MIN_NET_USD", "5.0")),
        "top_k": int(os.getenv("ARB_TOP_K", "5")),
        "sort_key": os.getenv("ARB_SORT_KEY", "net_roi_pct"),
        "sort_dir": os.getenv("ARB_SORT_DIR", "desc"),
    },
}

_EXEC_MODE = os.getenv("EXEC_MODE", "dry").lower()

_DEFAULT_SPOT = {
    "enabled": os.getenv("SPOT_ENABLED", "true").lower() == "true",
    "weights": {
        "micro_trend_scalper": float(os.getenv("SCALPER_WEIGHT", "0.40")),
        "scalping_breakout": float(os.getenv("BREAKOUT_WEIGHT", "0.25")),
        "bollinger_reversion": float(os.getenv("MEANREV_WEIGHT", "0.20")),
        "vwap_reversion": float(os.getenv("VWAP_WEIGHT", "0.10")),
        "liquidity_snipe": float(os.getenv("LIQ_SNIPE_WEIGHT", "0.05")),
    },
    "max_positions": int(os.getenv("MAX_CONCURRENT_POS", "5")),
    "max_trade_pct": float(os.getenv("MAX_TRADE_PCT", "0.20")),
    "risk_per_trade_pct": float(os.getenv("RISK_PER_TRADE_PCT", "0.005")),
    "max_symbol_exposure_pct": float(os.getenv("MAX_SYMBOL_EXPOSURE_PCT", "0.35")),
    "tp_pct_default": float(os.getenv("SPOT_TP_PCT_DEFAULT", "0.30")),
    "sl_pct_default": float(os.getenv("SPOT_SL_PCT_DEFAULT", "0.15")),
}

_DEFAULT_RESERVES = {
    "portfolio": float(os.getenv("PORTFOLIO_RESERVE_PCT", "0.15")),
    "arbitrage": float(os.getenv("ARB_RESERVE_PCT", "0.25")),
}

_DEFAULT_OPS = {
    "capital": {
        "cap_pct": float(os.getenv("CAPITAL_CAP_PCT", "0.25")),
        "hard_max_pct": float(os.getenv("CAPITAL_CAP_HARD_MAX_PCT", "1.0")),
    }
}

_DEFAULT_STATE: Dict[str, Any] = {
    "auto_mode": os.getenv("AUTO_MODE", "true").lower() == "true",
    "global_stop": os.getenv("GLOBAL_STOP", "false").lower() == "true",
    "trading_on": True,
    "agent_on": True,
    "arb_on": True,
    "sched_on": True,
    "manual_override": False,
    "manual_strategy": None,
    "exec_mode": _EXEC_MODE,
    "portfolio_equity": float(os.getenv("PORTFOLIO_EQUITY", "10000")),
    "scalp": deepcopy(_DEFAULT_SCALP),
    "arb": deepcopy(_DEFAULT_ARB),
    "spot": deepcopy(_DEFAULT_SPOT),
    "reserves": deepcopy(_DEFAULT_RESERVES),
    "ops": deepcopy(_DEFAULT_OPS),
}

_CURRENT_STATE: Dict[str, Any] | None = None


def _read_state_file() -> Dict[str, Any]:
    if not STATE_PATH.exists():
        return deepcopy(_DEFAULT_STATE)
    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            merged = deepcopy(_DEFAULT_STATE)
            for key, value in payload.items():
                if isinstance(merged.get(key), dict) and isinstance(value, dict):
                    merged[key].update(value)
                else:
                    merged[key] = value
            return merged
    except Exception as exc:  # pragma: no cover - corrupted state file
        logger.warning("Failed to read state file: %s", exc)
    return deepcopy(_DEFAULT_STATE)


def _write_state_file(state: Dict[str, Any]) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def _apply_arb_update(state: Dict[str, Any], payload: Dict[str, Any]) -> None:
    arb_state = state.get("arb") or {}
    filters = arb_state.setdefault("filters", deepcopy(_DEFAULT_ARB["filters"]))
    for key, value in payload.items():
        if key == "filters" and isinstance(value, dict):
            for f_key, f_value in value.items():
                parsed = _parse_filter_value(f_key, f_value, filters)
                if parsed is None:
                    continue
                if filters.get(f_key) == parsed:
                    continue
                filters[f_key] = parsed
                logger.info("state update arb.filters.%s=%s", f_key, parsed)
                arb_filter_changes_total.labels(field=f_key).inc()
        elif key in {"interval", "top_k"}:
            try:
                parsed_int = int(value)
            except (TypeError, ValueError):
                continue
            if parsed_int <= 0:
                continue
            arb_state[key] = parsed_int
            logger.info("state update arb.%s=%s", key, parsed_int)
            ops_state_changes_total.labels(key=f"arb.{key}").inc()
        elif key in {"qty_usd", "threshold_pct", "qty_min_usd", "qty_max_usd"}:
            try:
                parsed_float = float(value)
            except (TypeError, ValueError):
                continue
            if parsed_float <= 0:
                continue
            arb_state[key] = parsed_float
            logger.info("state update arb.%s=%s", key, parsed_float)
            ops_state_changes_total.labels(key=f"arb.{key}").inc()
        elif key == "auto_mode":
            arb_state[key] = bool(value)
            logger.info("state update arb.auto_mode=%s", arb_state[key])
            ops_state_changes_total.labels(key="arb.auto_mode").inc()
    state["arb"] = arb_state


def _apply_spot_update(state: Dict[str, Any], payload: Dict[str, Any]) -> None:
    spot_state = state.get("spot") or deepcopy(_DEFAULT_SPOT)
    for key, value in payload.items():
        if key == "weights" and isinstance(value, dict):
            for strat, weight in value.items():
                try:
                    parsed = float(weight)
                except (TypeError, ValueError):
                    continue
                spot_state.setdefault("weights", {})[strat] = parsed
                logger.info("state update spot.weights.%s=%.4f", strat, parsed)
                ops_state_changes_total.labels(key=f"spot.weights.{strat}").inc()
        elif key in {"enabled"}:
            spot_state[key] = bool(value)
            ops_state_changes_total.labels(key=f"spot.{key}").inc()
        elif key in {"max_positions"}:
            try:
                spot_state[key] = int(value)
            except (TypeError, ValueError):
                continue
            ops_state_changes_total.labels(key=f"spot.{key}").inc()
        elif key in {"max_trade_pct", "risk_per_trade_pct", "max_symbol_exposure_pct", "tp_pct_default", "sl_pct_default"}:
            try:
                spot_state[key] = float(value)
            except (TypeError, ValueError):
                continue
            ops_state_changes_total.labels(key=f"spot.{key}").inc()
    state["spot"] = spot_state


def _apply_reserve_update(state: Dict[str, Any], payload: Dict[str, Any]) -> None:
    reserves = state.get("reserves") or deepcopy(_DEFAULT_RESERVES)
    for key, value in payload.items():
        try:
            reserves[key] = float(value)
        except (TypeError, ValueError):
            continue
        ops_state_changes_total.labels(key=f"reserves.{key}").inc()
    state["reserves"] = reserves


def _apply_ops_update(state: Dict[str, Any], payload: Dict[str, Any]) -> None:
    ops_state = state.get("ops") or deepcopy(_DEFAULT_OPS)
    capital = ops_state.setdefault("capital", deepcopy(_DEFAULT_OPS["capital"]))
    if "capital" in payload and isinstance(payload["capital"], dict):
        for key, value in payload["capital"].items():
            try:
                capital[key] = float(value)
            except (TypeError, ValueError):
                continue
            if key == "cap_pct":
                hard_max = float(capital.get("hard_max_pct", _DEFAULT_OPS["capital"]["hard_max_pct"]))
                capital[key] = max(0.0, min(capital[key], hard_max))
            ops_state_changes_total.labels(key=f"ops.capital.{key}").inc()
    state["ops"] = ops_state


def _parse_filter_value(key: str, value: object, current: Dict[str, Any]) -> Any | None:
    if key in {"min_net_roi_pct", "max_net_roi_pct", "min_net_usd"}:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        if parsed < 0:
            parsed = 0.0
        return parsed
    if key == "top_k":
        try:
            parsed_int = int(value)
        except (TypeError, ValueError):
            return None
        if parsed_int <= 0:
            parsed_int = 1
        return parsed_int
    if key == "sort_key":
        parsed_key = str(value)
        if parsed_key not in _ARB_SORT_KEYS:
            return current.get(key)
        return parsed_key
    if key == "sort_dir":
        parsed_dir = str(value).lower()
        if parsed_dir not in _ARB_SORT_DIRS:
            return current.get(key)
        return parsed_dir
    return None


def _ensure_state_loaded() -> None:
    global _CURRENT_STATE
    if _CURRENT_STATE is None:
        _CURRENT_STATE = _read_state_file()
        ops_auto_mode.set(1.0 if _CURRENT_STATE.get("auto_mode") else 0.0)
        ops_global_stop.set(1.0 if _CURRENT_STATE.get("global_stop") else 0.0)


def get_state() -> Dict[str, Any]:
    """Return a copy of the current runtime state."""
    _ensure_state_loaded()
    return deepcopy(_CURRENT_STATE or _DEFAULT_STATE)


def set_state(update: Dict[str, Any]) -> Dict[str, Any]:
    """Merge provided keys into the runtime state."""
    _ensure_state_loaded()
    assert _CURRENT_STATE is not None  # for type-checkers
    state = _CURRENT_STATE
    changed: Dict[str, Any] = {}
    for key, value in update.items():
        if key not in state:
            continue
        if key == "arb" and isinstance(value, dict):
            _apply_arb_update(state, value)
            changed[key] = deepcopy(state[key])
            continue
        if key == "spot" and isinstance(value, dict):
            _apply_spot_update(state, value)
            changed[key] = deepcopy(state[key])
            continue
        if key == "reserves" and isinstance(value, dict):
            _apply_reserve_update(state, value)
            changed[key] = deepcopy(state[key])
            continue
        if key == "ops" and isinstance(value, dict):
            _apply_ops_update(state, value)
            changed[key] = deepcopy(state[key])
            continue
        if isinstance(state[key], dict) and isinstance(value, dict):
            state[key].update(value)
            changed[key] = deepcopy(state[key])
        else:
            if state[key] == value:
                continue
            state[key] = value
            changed[key] = value
        logger.info("state update %s=%s", key, state[key])
        ops_state_changes_total.labels(key=key).inc()
        if key == "auto_mode":
            ops_auto_mode.set(1.0 if bool(state[key]) else 0.0)
        if key == "global_stop":
            ops_global_stop.set(1.0 if bool(state[key]) else 0.0)
    _write_state_file(state)
    return get_state()


def reset_state() -> Dict[str, Any]:
    """Reset state to defaults (primarily for tests)."""
    global _CURRENT_STATE
    _CURRENT_STATE = deepcopy(_DEFAULT_STATE)
    _write_state_file(_CURRENT_STATE)
    return get_state()
