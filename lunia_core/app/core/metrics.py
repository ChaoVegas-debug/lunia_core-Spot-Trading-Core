"""Prometheus metrics helpers for Lunia core."""
from __future__ import annotations

import threading
from typing import Set

from prometheus_client import REGISTRY

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Summary,
    generate_latest,
    start_http_server,
)

def safe_create(cls, name, documentation, **kwargs):
    try:
        return cls(name, documentation, **kwargs)
    except ValueError:
        if name in REGISTRY._names_to_collectors:
            return REGISTRY._names_to_collectors[name]
        raise

signals_total = safe_create(Counter, 
    "lunia_signals_total",
    "Total trading signals generated",
    labelnames=("symbol", "side"),
)
orders_total = safe_create(Counter, 
    "lunia_orders_total",
    "Total orders submitted",
    labelnames=("symbol", "side"),
)
orders_rejected_total = safe_create(Counter, 
    "lunia_orders_rejected_total",
    "Total orders rejected by risk or execution",
    labelnames=("symbol", "side", "reason"),
)
api_latency_ms = safe_create(Histogram, 
    "lunia_api_latency_ms",
    "Latency of API handlers in milliseconds",
    buckets=(10, 25, 50, 100, 250, 500, 1000, 2000, 5000),
)
pnl_total = safe_create(Gauge, 
    "lunia_pnl_total",
    "Aggregated realized PnL (USD)",
)
ops_state_changes_total = safe_create(Counter, 
    "lunia_ops_state_changes_total",
    "Number of runtime state updates",
    labelnames=("key",),
)
ops_auto_mode = safe_create(Gauge, 
    "lunia_ops_auto_mode",
    "Auto mode flag (1=enabled)",
)
ops_global_stop = safe_create(Gauge, 
    "lunia_ops_global_stop",
    "Global stop flag (1=enabled)",
)
arbitrage_opportunities_total = safe_create(Counter, 
    "lunia_arbitrage_opportunities_total",
    "Total detected arbitrage opportunities",
    labelnames=("symbol", "buy", "sell"),
)
arbitrage_executed_total = safe_create(Counter, 
    "lunia_arbitrage_executed_total",
    "Total arbitrage executions by mode/status",
    labelnames=("mode", "status"),
)
arbitrage_avg_spread_pct = safe_create(Gauge, 
    "lunia_arbitrage_avg_spread_pct",
    "Average spread percentage of detected opportunities",
)
arbitrage_scan_latency_ms = safe_create(Histogram, 
    "lunia_arbitrage_scan_latency_ms",
    "Latency of arbitrage scans in milliseconds",
    buckets=(10, 25, 50, 100, 250, 500, 1000, 2000, 5000),
)
arbitrage_pnl_total = safe_create(Gauge, 
    "lunia_arbitrage_pnl_total",
    "Cumulative arbitrage PnL (USD)",
)
arb_scans_total = safe_create(Counter, 
    "lunia_arb_scans_total",
    "Total arbitrage scan attempts",
)
arb_proposals_total = safe_create(Counter, 
    "lunia_arb_proposals_total",
    "Total opportunities generated before filters",
)
arb_proposals_after_filter_total = safe_create(Counter, 
    "lunia_arb_proposals_after_filter_total",
    "Opportunities that survived filtering",
)
arb_filtered_out_total = safe_create(Counter, 
    "lunia_arb_filtered_out_total",
    "Opportunities filtered out",
    labelnames=("reason",),
)
arb_net_roi_pct_bucket = safe_create(Histogram, 
    "lunia_arb_net_roi_pct",
    "Distribution of net ROI percent",
    buckets=(0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0),
)
arb_net_profit_usd_bucket = safe_create(Histogram, 
    "lunia_arb_net_profit_usd",
    "Distribution of net profit (USD)",
    buckets=(1, 2, 5, 10, 25, 50, 100, 250, 500),
)
arb_qty_suggested_usd = safe_create(Histogram, 
    "lunia_arb_qty_suggested_usd",
    "Suggested arbitrage quantity in USD",
    buckets=(10, 25, 50, 75, 100, 150, 250, 500, 1000),
)
arb_execs_total = safe_create(Counter, 
    "lunia_arb_execs_total",
    "Arbitrage execution attempts",
    labelnames=("mode",),
)
arb_success_total = safe_create(Counter, 
    "lunia_arb_success_total",
    "Successful arbitrage executions",
    labelnames=("mode",),
)
arb_fail_total = safe_create(Counter, 
    "lunia_arb_fail_total",
    "Failed arbitrage executions",
    labelnames=("mode", "stage"),
)
arb_net_profit_total_usd = safe_create(Gauge, 
    "lunia_arb_net_profit_total_usd",
    "Accumulated arbitrage profit (USD)",
)
arb_auto_execs_total = safe_create(Counter, 
    "lunia_arb_auto_execs_total",
    "Automatic arbitrage executions",
    labelnames=("mode",),
)
arb_daily_pnl_usd = safe_create(Gauge, 
    "lunia_arb_daily_pnl_usd",
    "Daily arbitrage PnL (USD)",
)
arb_success_rate = safe_create(Gauge, 
    "lunia_arb_success_rate",
    "Ratio of successful executions over attempts",
)
arb_rate_limited_total = safe_create(Counter, 
    "lunia_arb_rate_limited_total",
    "Executions blocked by rate limits",
    labelnames=("reason",),
)
arb_filter_changes_total = safe_create(Counter, 
    "lunia_arb_filter_changes_total",
    "Updates to arbitrage filter configuration",
    labelnames=("field",),
)
arb_execution_latency_ms = safe_create(Summary, 
    "lunia_arb_execution_latency_ms",
    "Execution latency in milliseconds",
    labelnames=("mode",),
)
ops_capital_cap_pct = safe_create(Gauge, 
    "lunia_ops_capital_cap_pct",
    "Configured capital cap percentage",
)
equity_total_usd = safe_create(Gauge, 
    "lunia_equity_total_usd",
    "Total estimated equity in USD",
)
tradable_equity_usd = safe_create(Gauge, 
    "lunia_tradable_equity_usd",
    "Tradable equity after cap and reserves",
)
spot_trades_total = safe_create(Counter, 
    "lunia_spot_trades_total",
    "Total executed spot trades",
    labelnames=("strategy", "symbol", "side"),
)
spot_pnl_total_usd = safe_create(Gauge, 
    "lunia_spot_pnl_total_usd",
    "Aggregate realized spot trading PnL (USD)",
)
spot_daily_pnl_usd = safe_create(Gauge, 
    "lunia_spot_daily_pnl_usd",
    "Daily realized spot PnL (USD)",
)
spot_positions_open = safe_create(Gauge, 
    "lunia_spot_positions_open",
    "Number of open spot positions",
)
spot_success_rate_pct = safe_create(Gauge, 
    "lunia_spot_success_rate_pct",
    "Spot trading success rate percentage",
)
spot_alloc_strategy_usd = safe_create(Gauge, 
    "lunia_spot_alloc_strategy_usd",
    "Allocated budget per spot strategy",
    labelnames=("strategy",),
)
spot_risk_reject_total = safe_create(Counter, 
    "lunia_spot_risk_reject_total",
    "Spot signals rejected by risk checks",
    labelnames=("reason",),
)
ai_research_runs_total = safe_create(Counter, 
    "lunia_ai_research_runs_total",
    "Number of AI research executions",
    labelnames=("mode",),
)
ai_research_confidence_avg = safe_create(Gauge, 
    "lunia_ai_research_confidence_avg",
    "Average confidence of the last AI research run",
)
ai_research_signal_total = safe_create(Counter, 
    "lunia_ai_research_signal_total",
    "Total research signals by strategy/bias",
    labelnames=("strategy", "bias"),
)
ai_priority_signal_total = safe_create(Counter, 
    "lunia_ai_priority_signal_total",
    "Priority signals influenced by AI forecast",
    labelnames=("pair", "bias"),
)
bot_commands_total = safe_create(Counter, 
    "lunia_bot_commands_total",
    "Total Telegram bot commands handled",
    labelnames=("command",),
)
bot_errors_total = safe_create(Counter, 
    "lunia_bot_errors_total",
    "Telegram bot errors",
)
bot_latency_ms = safe_create(Histogram, 
    "lunia_bot_latency_ms",
    "Telegram bot command latency in milliseconds",
    buckets=(10, 25, 50, 100, 250, 500, 1000),
)
s3_exports_total = safe_create(Counter, 
    "lunia_s3_exports_total",
    "Total S3/MinIO exports",
    labelnames=("status",),
)
s3_export_last_status = safe_create(Gauge, 
    "lunia_s3_export_last_status",
    "Status of the most recent S3 export (1=success,0=failure)",
)
alerts_sent_total = safe_create(Counter, 
    "lunia_alerts_sent_total",
    "Alerts sent to operators",
    labelnames=("level",),
)

_metrics_lock = threading.Lock()
_started_servers: Set[int] = set()


def ensure_metrics_server(port: int) -> None:
    """Start a Prometheus metrics HTTP server if not already running."""
    with _metrics_lock:
        if port in _started_servers:
            return
        try:
            start_http_server(port)
            _started_servers.add(port)
        except OSError:
            # Port already in use, likely from reloader or another process.
            # We treat this as "already started" to avoid crashing.
            pass


def scrape_metrics() -> bytes:
    """Expose metrics for frameworks that need raw payloads."""
    return generate_latest()
