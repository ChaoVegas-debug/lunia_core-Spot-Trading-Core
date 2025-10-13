"""Formatting helpers for Telegram arbitrage interface."""
from __future__ import annotations

from typing import Dict, Iterable, List

from app.core.state import get_state

from .scanner import ArbitrageFilters, ArbitrageOpportunity


def format_opportunity(opportunity: ArbitrageOpportunity, index: int) -> str:
    meta = opportunity.meta
    fees = meta.get("fees", {})
    transfer = meta.get("transfer", {})
    lines = [
        f"♻️ Arb #{index} — {opportunity.symbol}",
        f"Buy {opportunity.buy_exchange} @ {opportunity.buy_price:.2f} → Sell {opportunity.sell_exchange} @ {opportunity.sell_price:.2f}",
        (
            "Qty: ${qty:.2f} | gross: {gross:.2f}% | fees: {fees:.2f}% | slip: {slip:.2f}% | "
            "net: {net:.2f}% | net_usd: ${net_usd:.2f}"
        ).format(
            qty=opportunity.qty_usd,
            gross=opportunity.gross_spread_pct,
            fees=opportunity.fees_total_pct,
            slip=opportunity.slippage_est_pct,
            net=opportunity.net_roi_pct,
            net_usd=opportunity.net_profit_usd,
        ),
        "ETA: {eta}s via {transfer_type}".format(
            eta=int(transfer.get("eta_sec", 0)), transfer_type=opportunity.transfer_type
        ),
        "Fees: taker_buy={:.2f}% taker_sell={:.2f}% transfer=${:.2f}".format(
            float(fees.get("taker_buy_pct", 0.0)),
            float(fees.get("taker_sell_pct", 0.0)),
            float(fees.get("transfer_fee_usd", 0.0)),
        ),
    ]
    return "\n".join(lines)


def build_buttons(top: int, auto_mode: bool, exec_mode: str) -> List[List[Dict[str, str]]]:
    rows: List[List[Dict[str, str]]] = []
    select_row = [{"text": f"Выбрать {i+1}", "callback_data": f"arb_select:{i}"} for i in range(top)]
    rows.append(select_row)
    rows.append(
        [
            {"text": "ROI 0.5%", "callback_data": "arb_preset:0.5"},
            {"text": "ROI 1%", "callback_data": "arb_preset:1.0"},
            {"text": "ROI 2%", "callback_data": "arb_preset:2.0"},
            {"text": "ROI 3%", "callback_data": "arb_preset:3.0"},
        ]
    )
    rows.append(
        [
            {"text": "Сделать", "callback_data": "arb_exec"},
            {"text": "Сделать+Перевести", "callback_data": "arb_exec_transfer"},
            {"text": "Dry-Run" if exec_mode != "dry" else "Real?", "callback_data": "arb_toggle_exec"},
        ]
    )
    rows.append(
        [
            {"text": "Sort ROI", "callback_data": "arb_sort:roi"},
            {"text": "Sort $", "callback_data": "arb_sort:usd"},
            {"text": "↻ Обновить", "callback_data": "arb_scan"},
            {"text": "/daily", "callback_data": "arb_daily"},
        ]
    )
    rows.append(
        [
            {
                "text": "Авто:Выкл" if auto_mode else "Авто:Вкл",
                "callback_data": "arb_toggle_auto",
            },
            {"text": "Стоп", "callback_data": "arb_stop"},
            {"text": "Экспорт", "callback_data": "arb_export"},
        ]
    )
    return rows


def format_filters(filters: ArbitrageFilters) -> str:
    state = get_state()
    arb = state.get("arb", {})
    qty = arb.get("qty_usd", 0.0)
    min_qty = arb.get("qty_min_usd", qty)
    max_qty = arb.get("qty_max_usd", qty)
    return (
        "Filters: ROI {min:.2f}-{max:.2f}% | $≥{usd:.2f} | Sort: {key} {dir} | Top {top} | Qty: adaptive ({min_qty:.0f}-{max_qty:.0f})"
    ).format(
        min=filters.min_net_roi_pct,
        max=filters.max_net_roi_pct,
        usd=filters.min_net_usd,
        key=filters.sort_key,
        dir="↓" if filters.sort_dir == "desc" else "↑",
        top=filters.top_k,
        min_qty=min_qty,
        max_qty=max_qty,
    )


def summarize_opportunities(opportunities: Iterable[ArbitrageOpportunity]) -> str:
    parts = [format_opportunity(opp, idx + 1) for idx, opp in enumerate(opportunities)]
    return "\n\n".join(parts) if parts else "Нет доступных возможностей"


__all__ = [
    "format_opportunity",
    "build_buttons",
    "format_filters",
    "summarize_opportunities",
]
