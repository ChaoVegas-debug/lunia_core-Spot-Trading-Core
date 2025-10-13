"""Telegram bot with operational controls and reporting."""
from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from app.compat.dotenv import load_dotenv

from ...core.metrics import bot_commands_total, bot_errors_total, bot_latency_ms
from ...core.state import get_state, set_state
from ...db.reporting import arbitrage_daily_summary, equity_curve, list_trades, pnl_summary
from ...services.arbitrage.worker import (
    get_filters as get_arbitrage_filters,
    get_state as get_arbitrage_state,
    scan_now as arbitrage_scan_now,
    toggle_auto_mode as toggle_arbitrage_auto,
    update_filters as update_arbitrage_filters,
)
from ...services.arbitrage.ui import (
    build_buttons as build_arbitrage_buttons,
    format_filters as format_arbitrage_filters,
    summarize_opportunities as summarize_arbitrage_ops,
)
from ...services.reports.charts import plot_equity_curve
from ...services.reports.exporter import get_exporter
from ...services.guard.alerts import evaluate_and_alert
from ..api.flask_app import agent, supervisor

load_dotenv()

try:  # pragma: no cover - optional dependency
    from aiogram import Bot, Dispatcher, types
    from aiogram.enums import ParseMode
    from aiogram.filters import Command
    from aiogram.fsm.storage.memory import MemoryStorage
except Exception:  # pragma: no cover - offline fallback
    Bot = None  # type: ignore
    Dispatcher = None  # type: ignore
    types = SimpleNamespace(Message=SimpleNamespace(reply=lambda *a, **k: None))  # type: ignore
    ParseMode = SimpleNamespace(HTML="HTML")  # type: ignore

    def Command(*_args, **_kwargs):  # type: ignore
        def decorator(func: Callable):
            return func

        return decorator

    class MemoryStorage:  # type: ignore
        pass

LOG_DIR = Path(__file__).resolve().parents[4] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
BOT_LOG = LOG_DIR / "telegram.log"
EXPORT_DIR = LOG_DIR / "exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.FileHandler(BOT_LOG, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")


def _format_state() -> str:
    state = get_state()
    lines = [
        f"Auto mode: {'ON' if state['auto_mode'] else 'OFF'}",
        f"Global stop: {'ON' if state['global_stop'] else 'OFF'}",
        f"Trading: {'ON' if state['trading_on'] else 'OFF'}",
        f"Arbitrage: {'ON' if state['arb_on'] else 'OFF'}",
        f"Scheduler: {'ON' if state['sched_on'] else 'OFF'}",
        f"Manual override: {'ON' if state['manual_override'] else 'OFF'}",
        f"Scalp TP/SL/Qty: {state['scalp']['tp_pct']} / {state['scalp']['sl_pct']} / {state['scalp']['qty_usd']}",
        f"Arb interval/threshold/qty: {state['arb']['interval']} / {state['arb']['threshold_pct']} / {state['arb']['qty_usd']}",
        f"Arb filters: {format_arbitrage_filters(get_arbitrage_filters())}",
    ]
    return "\n".join(lines)


def arbitrage_filters_summary() -> str:
    return format_arbitrage_filters(get_arbitrage_filters())


def update_arbitrage_filter(field: str, value: float | str) -> Dict[str, object]:
    mapping = {
        "minroi": "min_net_roi_pct",
        "maxroi": "max_net_roi_pct",
        "minusd": "min_net_usd",
        "top": "top_k",
        "sort": "sort_key",
        "sortdir": "sort_dir",
    }
    key = mapping.get(field.lower())
    if key is None:
        raise ValueError("Unsupported filter field")
    update_arbitrage_filters({key: value})
    return get_state()


def arbitrage_overview(limit: int = 5) -> Dict[str, object]:
    limit = max(1, limit)
    arbitrage_scan_now()
    runtime = get_arbitrage_state()
    filters = get_arbitrage_filters()
    summary = summarize_arbitrage_ops(runtime.last_objects[:limit])
    state = get_state()
    buttons = build_arbitrage_buttons(limit, bool(state["arb"]["auto_mode"]), state["exec_mode"])
    return {
        "summary": summary,
        "filters": format_arbitrage_filters(filters),
        "buttons": buttons,
    }


def apply_roi_preset(threshold_pct: float) -> Dict[str, object]:
    update_arbitrage_filters({"min_net_roi_pct": threshold_pct})
    return get_state()


def set_sorting(key: str, direction: Optional[str] = None) -> Dict[str, object]:
    payload: Dict[str, object] = {}
    if key == "roi":
        payload["sort_key"] = "net_roi_pct"
    elif key == "usd":
        payload["sort_key"] = "net_profit_usd"
    if direction:
        payload["sort_dir"] = direction
    if payload:
        update_arbitrage_filters(payload)
    return get_state()


def daily_summary_text() -> str:
    stats = arbitrage_daily_summary()
    evaluate_and_alert(stats)
    pnl_icon = "✅" if stats.get("avg_roi", 0.0) >= 1.0 else ("⚠️" if stats.get("avg_roi", 0.0) >= 0.5 else "❌")
    fail_icon = "❌" if stats.get("fail", 0) >= float(os.getenv("ALERTS_FAIL_THRESHOLD", "5")) else "✅"
    lines = [
        "📊 Daily Arbitrage Summary",
        f"P&L: ${stats['pnl']:.2f}",
        f"Success: {stats['success']} | Fail: {stats['fail']} ({stats['success_rate']*100:.1f}%)",
        f"Avg ROI: {stats['avg_roi']:.2f}% {pnl_icon}",
        f"Failure threshold check: {fail_icon}",
    ]
    return "\n".join(lines)


def manual_export() -> Dict[str, str]:
    exporter = get_exporter()
    if exporter is None:
        raise RuntimeError("Exporter is not configured")
    return exporter.export_now()


def set_arbitrage_auto(enabled: bool) -> Dict[str, object]:
    toggle_arbitrage_auto(enabled)
    return get_state()


def set_capital_pct(pct: float) -> Dict[str, object]:
    pct = max(0.0, min(1.0, float(pct)))
    return set_state({"ops": {"capital": {"cap_pct": pct}}})


def adjust_capital_pct(delta: float) -> Dict[str, object]:
    state = get_state()
    current = float(state.get("ops", {}).get("capital", {}).get("cap_pct", 0.25))
    return set_capital_pct(current + delta)


def toggle_spot(enabled: bool) -> Dict[str, object]:
    return set_state({"spot": {"enabled": enabled}})


def update_strategy_weight(name: str, weight: float) -> Dict[str, object]:
    state = get_state()
    weights = state.get("spot", {}).get("weights", {}).copy()
    weights[name] = float(weight)
    return set_state({"spot": {"weights": weights}})


def spot_status() -> Dict[str, object]:
    state = get_state()
    snapshot = {
        "enabled": state.get("spot", {}).get("enabled", True),
        "weights": state.get("spot", {}).get("weights", {}),
        "cap_pct": state.get("ops", {}).get("capital", {}).get("cap_pct", 0.25),
        "reserves": state.get("reserves", {}),
    }
    return snapshot


def build_status_report() -> str:
    active = {name: cfg for name, cfg in supervisor.price_history.__dict__.items() if cfg}
    report = ["<b>Lunia Status</b>", _format_state()]
    positions = agent.portfolio.positions
    if positions:
        position_lines = []
        for symbol, pos in positions.items():
            position_lines.append(
                f"{symbol}: qty={pos.quantity:.6f} avg={pos.average_price:.2f} uPnL={agent.portfolio.unrealized_pnl(symbol):.2f}"
            )
        report.append("<b>Positions</b>\n" + "\n".join(position_lines))
    report.append("<i>Signals buffered:</i> %s" % len(agent.supervisor.price_history))
    return "\n\n".join(report)


def update_scalp_setting(field: str, value: float) -> Dict[str, object]:
    field = field.lower()
    valid = {"tp": "tp_pct", "sl": "sl_pct", "qty": "qty_usd"}
    if field not in valid:
        raise ValueError("field must be tp, sl or qty")
    return set_state({"scalp": {valid[field]: float(value)}})


def update_arb_setting(field: str, value: float) -> Dict[str, object]:
    field = field.lower()
    mapping = {"interval": "interval", "threshold": "threshold_pct", "qty": "qty_usd"}
    if field not in mapping:
        raise ValueError("field must be interval, threshold or qty")
    return set_state({"arb": {mapping[field]: float(value)}})


def pnl_report(period: str, symbol: Optional[str] = None) -> str:
    data = pnl_summary(period=period, symbol=symbol)
    return f"PnL {period}: {data['pnl']:.2f} USD"


def recent_trades(limit: int = 5) -> List[Dict[str, object]]:
    return list_trades(limit=limit)


def equity_chart(period: str = "day", group: str = "hour") -> bytes:
    curve = equity_curve(period=period, group=group)
    return plot_equity_curve(curve)


async def _ensure_admin(message: "types.Message") -> bool:
    if not ADMIN_CHAT_ID:
        await message.answer("ADMIN_CHAT_ID is not configured")
        return False
    if str(message.chat.id) != str(ADMIN_CHAT_ID):
        await message.answer("Unauthorized")
        bot_errors_total.inc()
        logger.warning("Unauthorized access chat_id=%s", message.chat.id)
        return False
    return True


async def _execute_command(name: str, message: "types.Message", handler: Callable[[], asyncio.Future | asyncio.Task | None]) -> None:
    start = time.time()
    try:
        await handler()
        bot_commands_total.labels(command=name).inc()
    except Exception as exc:  # pragma: no cover - runtime guard
        bot_errors_total.inc()
        logger.exception("Bot command %s failed: %s", name, exc)
        await message.answer(f"Error: {exc}")
    finally:
        bot_latency_ms.observe((time.time() - start) * 1000)


def _format_trades(trades: Iterable[Dict[str, object]]) -> str:
    rows = list(trades)
    if not rows:
        return "No trades available"
    lines = []
    for row in rows:
        lines.append(
            f"{row['timestamp']}: {row['symbol']} {row['side']} qty={row['qty']} price={row['price']:.2f} pnl={row['pnl']:.2f}"
        )
    return "\n".join(lines)


def create_dispatcher() -> "Dispatcher":
    if Dispatcher is None:  # pragma: no cover
        raise RuntimeError("aiogram is not installed")
    dp = Dispatcher(storage=MemoryStorage())

    @dp.message(Command(commands=["help"]))
    async def cmd_help(message: "types.Message") -> None:
        if not await _ensure_admin(message):
            return
        text = (
            "Commands:\n"
            "/status /auto_on /auto_off /stop_all /start_all /trading_on /trading_off\n"
            "/arb_on /arb_off /scalp /scalp_set /arb_interval /arb_threshold /arb_qty\n"
            "/arb_filter /arb_filters /arb_sort /arb_sortdir /daily /export /alerts\n"
            "/pnl /equity /trades /export_csv /export_json"
        )
        await message.answer(text, parse_mode=ParseMode.HTML)

    @dp.message(Command(commands=["status"]))
    async def cmd_status(message: "types.Message") -> None:
        if not await _ensure_admin(message):
            return
        await message.answer(build_status_report(), parse_mode=ParseMode.HTML)

    async def _toggle(key: str, value: bool, message: "types.Message") -> None:
        if not await _ensure_admin(message):
            return
        set_state({key: value})
        await message.answer(_format_state())

    for cmd, (key, value) in {
        "auto_on": ("auto_mode", True),
        "auto_off": ("auto_mode", False),
        "stop_all": ("global_stop", True),
        "start_all": ("global_stop", False),
        "trading_on": ("trading_on", True),
        "trading_off": ("trading_on", False),
        "arb_on": ("arb_on", True),
        "arb_off": ("arb_on", False),
        "sched_on": ("sched_on", True),
        "sched_off": ("sched_on", False),
    }.items():
        @dp.message(Command(commands=[cmd]))
        async def handler(message: "types.Message", key=key, value=value) -> None:  # type: ignore
            await _toggle(key, value, message)

    @dp.message(Command(commands=["scalp"]))
    async def cmd_scalp(message: "types.Message") -> None:
        if not await _ensure_admin(message):
            return
        await message.answer(_format_state())

    @dp.message(Command(commands=["scalp_set"]))
    async def cmd_scalp_set(message: "types.Message") -> None:
        if not await _ensure_admin(message):
            return
        parts = message.text.split()
        if len(parts) != 3:
            await message.answer("Usage: /scalp_set <tp|sl|qty> <value>")
            return
        try:
            update_scalp_setting(parts[1], float(parts[2]))
        except ValueError as exc:
            await message.answer(str(exc))
            return
        await message.answer(_format_state())

    for cmd, field in {"arb_interval": "interval", "arb_threshold": "threshold", "arb_qty": "qty"}.items():
        @dp.message(Command(commands=[cmd]))
        async def handler(message: "types.Message", field=field, cmd=cmd) -> None:  # type: ignore
            if not await _ensure_admin(message):
                return
            parts = message.text.split()
            if len(parts) != 2:
                await message.answer(f"Usage: /{cmd} <value>")
                return
            try:
                update_arb_setting(field, float(parts[1]))
            except ValueError as exc:
                await message.answer(str(exc))
                return
            await message.answer(_format_state())

    @dp.message(Command(commands=["arb_filter"]))
    async def cmd_arb_filter(message: "types.Message") -> None:
        if not await _ensure_admin(message):
            return
        parts = message.text.split()
        if len(parts) != 3:
            await message.answer("Usage: /arb_filter <minroi|maxroi|minusd|top> <value>")
            return
        try:
            update_arbitrage_filter(parts[1], float(parts[2]) if parts[1] != "top" else int(parts[2]))
        except ValueError as exc:
            await message.answer(str(exc))
            return
        await message.answer(arbitrage_filters_summary())

    @dp.message(Command(commands=["arb_filters"]))
    async def cmd_arb_filters(message: "types.Message") -> None:
        if not await _ensure_admin(message):
            return
        await message.answer(arbitrage_filters_summary())

    @dp.message(Command(commands=["arb_sort"]))
    async def cmd_arb_sort(message: "types.Message") -> None:
        if not await _ensure_admin(message):
            return
        parts = message.text.split()
        key = parts[1] if len(parts) > 1 else "roi"
        set_sorting("usd" if key.lower().startswith("u") else "roi")
        await message.answer(arbitrage_filters_summary())

    @dp.message(Command(commands=["arb_sortdir"]))
    async def cmd_arb_sortdir(message: "types.Message") -> None:
        if not await _ensure_admin(message):
            return
        parts = message.text.split()
        direction = parts[1] if len(parts) > 1 else "desc"
        set_sorting("roi", direction=direction.lower())
        await message.answer(arbitrage_filters_summary())

    @dp.message(Command(commands=["pnl"]))
    async def cmd_pnl(message: "types.Message") -> None:
        if not await _ensure_admin(message):
            return
        parts = message.text.split()
        period = parts[1] if len(parts) > 1 else "day"
        await message.answer(pnl_report(period))

    @dp.message(Command(commands=["trades"]))
    async def cmd_trades(message: "types.Message") -> None:
        if not await _ensure_admin(message):
            return
        trades = _format_trades(recent_trades())
        await message.answer(trades)

    @dp.message(Command(commands=["daily"]))
    async def cmd_daily(message: "types.Message") -> None:
        if not await _ensure_admin(message):
            return
        await message.answer(daily_summary_text())

    @dp.message(Command(commands=["export"]))
    async def cmd_export(message: "types.Message") -> None:
        if not await _ensure_admin(message):
            return
        result = manual_export()
        await message.answer(f"Exported {result['key']} ({result['status']})")

    @dp.message(Command(commands=["alerts"]))
    async def cmd_alerts(message: "types.Message") -> None:
        if not await _ensure_admin(message):
            return
        await message.answer(daily_summary_text())

    return dp


async def run_bot() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    if Bot is None:  # pragma: no cover
        raise RuntimeError("aiogram is not installed")
    bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
    dp = create_dispatcher()
    logger.info("Starting Telegram bot polling")
    await dp.start_polling(bot)


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(run_bot())
