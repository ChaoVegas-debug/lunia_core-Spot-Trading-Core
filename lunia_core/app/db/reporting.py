"""SQLite reporting helpers for Lunia core."""
from __future__ import annotations

import csv
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Iterator, List, Optional

from app.compat.dotenv import load_dotenv

if TYPE_CHECKING:  # pragma: no cover - type hints only
    from app.services.arbitrage.executor_safe import ArbitrageExecutionResult
    from app.services.arbitrage.scanner import ArbitrageOpportunity

load_dotenv()

_DEFAULT_DB = "sqlite:///./app/db/lunia.db"
_DB_URL = os.getenv("DB_URL", _DEFAULT_DB)


def _resolve_sqlite_path(url: str) -> Path:
    if not url.startswith("sqlite:///"):
        raise ValueError("Only sqlite URLs are supported in offline mode")
    raw_path = url.replace("sqlite:///", "", 1)
    path = Path(raw_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


_DB_PATH = _resolve_sqlite_path(_DB_URL)


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _init() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                qty REAL NOT NULL,
                price REAL NOT NULL,
                pnl REAL NOT NULL,
                strategy TEXT,
                mode TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS arbitrage_proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proposal_id TEXT NOT NULL,
                ts TEXT NOT NULL,
                symbol TEXT NOT NULL,
                buy_exchange TEXT NOT NULL,
                sell_exchange TEXT NOT NULL,
                qty_usd REAL NOT NULL,
                gross_spread_pct REAL NOT NULL,
                fees_total_pct REAL NOT NULL,
                slippage_est_pct REAL NOT NULL,
                net_roi_pct REAL NOT NULL,
                net_profit_usd REAL NOT NULL,
                filtered_out INTEGER NOT NULL DEFAULT 0,
                filter_reason TEXT,
                meta_json TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS arbitrage_execs (
                exec_id TEXT PRIMARY KEY,
                proposal_id TEXT NOT NULL,
                ts TEXT NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                pnl_usd REAL NOT NULL,
                fees_usd REAL NOT NULL,
                auto_trigger INTEGER NOT NULL,
                payload_json TEXT
            )
            """
        )


_init()


def record_trade(
    *,
    timestamp: Optional[str],
    symbol: str,
    side: str,
    qty: float,
    price: float,
    pnl: float,
    strategy: str | None = None,
    mode: str | None = None,
) -> None:
    ts = timestamp or datetime.utcnow().isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO trades (timestamp, symbol, side, qty, price, pnl, strategy, mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (ts, symbol, side, qty, price, pnl, strategy, mode),
        )


def record_arbitrage_proposal(
    opportunity: "ArbitrageOpportunity",
    *,
    filtered_out: bool,
    reason: Optional[str],
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO arbitrage_proposals (
                proposal_id, ts, symbol, buy_exchange, sell_exchange, qty_usd,
                gross_spread_pct, fees_total_pct, slippage_est_pct, net_roi_pct,
                net_profit_usd, filtered_out, filter_reason, meta_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                opportunity.proposal_id,
                datetime.utcnow().isoformat(),
                opportunity.symbol,
                opportunity.buy_exchange,
                opportunity.sell_exchange,
                opportunity.qty_usd,
                opportunity.gross_spread_pct,
                opportunity.fees_total_pct,
                opportunity.slippage_est_pct,
                opportunity.net_roi_pct,
                opportunity.net_profit_usd,
                1 if filtered_out else 0,
                reason,
                json.dumps(opportunity.meta),
            ),
        )


def record_arbitrage_execution(result: "ArbitrageExecutionResult", *, auto_trigger: bool) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO arbitrage_execs (
                exec_id, proposal_id, ts, mode, status, pnl_usd, fees_usd, auto_trigger, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.exec_id,
                result.proposal_id,
                datetime.utcnow().isoformat(),
                result.mode,
                result.status,
                result.pnl_usd,
                result.fees_usd,
                1 if auto_trigger else 0,
                json.dumps(result.to_dict()),
            ),
        )


def arbitrage_daily_pnl() -> float:
    start_ts = (datetime.utcnow() - timedelta(days=1)).isoformat()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT SUM(pnl_usd) AS pnl
            FROM arbitrage_execs
            WHERE datetime(ts) >= datetime(?) AND status = 'FILLED'
            """,
            (start_ts,),
        ).fetchone()
    return float(row["pnl"] or 0.0)


def arbitrage_success_counts() -> Dict[str, int]:
    start_ts = (datetime.utcnow() - timedelta(days=1)).isoformat()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT status, COUNT(*) as cnt
            FROM arbitrage_execs
            WHERE datetime(ts) >= datetime(?)
            GROUP BY status
            """,
            (start_ts,),
        ).fetchall()
    data = {row["status"]: int(row["cnt"]) for row in rows}
    return {
        "filled": data.get("FILLED", 0),
        "failed": data.get("FAILED", 0) + data.get("REJECTED", 0),
    }


def arbitrage_daily_summary() -> Dict[str, object]:
    pnl = arbitrage_daily_pnl()
    counts = arbitrage_success_counts()
    total = max(1, counts["filled"] + counts["failed"])
    avg_roi = 0.0
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT AVG(net_roi_pct) as avg_roi
            FROM arbitrage_proposals
            WHERE datetime(ts) >= datetime(?) AND filtered_out = 0
            """,
            ((datetime.utcnow() - timedelta(days=1)).isoformat(),),
        ).fetchone()
        if row and row["avg_roi"] is not None:
            avg_roi = float(row["avg_roi"])
    return {
        "pnl": pnl,
        "success": counts["filled"],
        "fail": counts["failed"],
        "success_rate": counts["filled"] / total,
        "avg_roi": avg_roi,
    }


def fetch_arbitrage_records(limit: int = 1000, table: str = "proposals") -> List[Dict[str, object]]:
    if table not in {"proposals", "execs"}:
        raise ValueError("table must be proposals or execs")
    if table == "proposals":
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM arbitrage_proposals
                ORDER BY datetime(ts) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    else:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM arbitrage_execs
                ORDER BY datetime(ts) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    return [dict(row) for row in rows]


def list_arbitrage_proposals(limit: int = 20) -> List[Dict[str, object]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT proposal_id, ts, symbol, buy_exchange, sell_exchange, net_roi_pct, net_profit_usd,
                   filtered_out, filter_reason
            FROM arbitrage_proposals
            ORDER BY datetime(ts) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_arbitrage_executions(limit: int = 20) -> List[Dict[str, object]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT exec_id, proposal_id, ts, mode, status, pnl_usd, fees_usd, auto_trigger
            FROM arbitrage_execs
            ORDER BY datetime(ts) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def _period_start(period: str) -> datetime:
    now = datetime.utcnow()
    if period == "day":
        return now - timedelta(days=1)
    if period == "week":
        return now - timedelta(weeks=1)
    if period == "month":
        return now - timedelta(days=30)
    if period == "year":
        return now - timedelta(days=365)
    return datetime.min


def list_trades(limit: int = 50, **filters: str) -> List[Dict[str, object]]:
    query = "SELECT timestamp, symbol, side, qty, price, pnl, strategy, mode FROM trades"
    clauses: List[str] = []
    params: List[object] = []
    for key in ("symbol", "strategy", "mode"):
        if key in filters and filters[key]:
            clauses.append(f"{key} = ?")
            params.append(filters[key])
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY datetime(timestamp) DESC LIMIT ?"
    params.append(limit)
    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def pnl_summary(period: str = "day", **filters: str) -> Dict[str, float]:
    start_ts = _period_start(period).isoformat()
    query = "SELECT SUM(pnl) as pnl FROM trades WHERE datetime(timestamp) >= datetime(?)"
    params: List[object] = [start_ts]
    for key in ("symbol", "strategy", "mode"):
        if key in filters and filters[key]:
            query += f" AND {key} = ?"
            params.append(filters[key])
    with _connect() as conn:
        row = conn.execute(query, params).fetchone()
    return {"period": period, "pnl": float(row["pnl"] or 0.0)}


def equity_curve(period: str = "day", group: str = "hour") -> List[Dict[str, object]]:
    start_ts = _period_start(period).isoformat()
    group_fmt = "%Y-%m-%d %H:00:00" if group == "hour" else "%Y-%m-%d"
    query = (
        "SELECT strftime(?, timestamp) AS bucket, SUM(pnl) as pnl "
        "FROM trades WHERE datetime(timestamp) >= datetime(?) "
        "GROUP BY bucket ORDER BY bucket"
    )
    with _connect() as conn:
        rows = conn.execute(query, (group_fmt, start_ts)).fetchall()
    cumulative = 0.0
    curve: List[Dict[str, object]] = []
    for row in rows:
        cumulative += float(row["pnl"] or 0.0)
        curve.append({"ts": row["bucket"], "equity": cumulative})
    return curve


def export_trades_csv(path: Path, **filters: str) -> Path:
    rows = list_trades(limit=10_000, **filters)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["timestamp", "symbol", "side", "qty", "price", "pnl", "strategy", "mode"]
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})
    return path


def export_trades_json(path: Path, **filters: str) -> Path:
    rows = list_trades(limit=10_000, **filters)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return path


__all__ = [
    "record_trade",
    "record_arbitrage_proposal",
    "record_arbitrage_execution",
    "arbitrage_daily_pnl",
    "arbitrage_success_counts",
    "arbitrage_daily_summary",
    "fetch_arbitrage_records",
    "list_arbitrage_proposals",
    "list_arbitrage_executions",
    "list_trades",
    "pnl_summary",
    "equity_curve",
    "export_trades_csv",
    "export_trades_json",
]
