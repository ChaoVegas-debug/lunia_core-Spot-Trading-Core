import importlib
import importlib
from pathlib import Path

import pytest

from app.core.portfolio.portfolio import Portfolio
from app.services.arbitrage.executor_safe import ArbitrageExecutionResult
from app.services.arbitrage.scanner import ArbitrageOpportunity


@pytest.fixture
def temp_reporting(monkeypatch, tmp_path):
    db_path = tmp_path / "reporting.db"
    monkeypatch.setenv("DB_URL", f"sqlite:///{db_path}")
    import app.db.reporting as reporting  # type: ignore
    reporting = importlib.reload(reporting)
    import app.core.portfolio as portfolio_package  # type: ignore
    importlib.reload(portfolio_package)
    from app.core.portfolio import portfolio as portfolio_module  # type: ignore
    monkeypatch.setattr(portfolio_module, "record_trade", reporting.record_trade)
    yield reporting


def test_reporting_records_trades(temp_reporting):
    portfolio = Portfolio()
    portfolio.update_on_fill("BTCUSDT", "BUY", 0.1, 20000)
    portfolio.update_on_fill("BTCUSDT", "SELL", 0.1, 21000)

    trades = temp_reporting.list_trades()
    assert len(trades) == 2
    summary = temp_reporting.pnl_summary("all")
    assert summary["pnl"] >= 0
    curve = temp_reporting.equity_curve("all")
    assert isinstance(curve, list)


def test_reporting_arbitrage_entries(temp_reporting):
    opportunity = ArbitrageOpportunity(
        proposal_id="test",
        symbol="BTCUSDT",
        buy_exchange="binance",
        sell_exchange="okx",
        buy_price=100.0,
        sell_price=101.0,
        gross_spread_pct=1.0,
        fees_total_pct=0.5,
        slippage_est_pct=0.1,
        net_roi_pct=0.4,
        net_profit_usd=0.4,
        qty_usd=100.0,
        created_at=0.0,
        transfer_type="internal",
        latency_ms=10.0,
        meta={},
    )
    temp_reporting.record_arbitrage_proposal(opportunity, filtered_out=False, reason=None)
    proposals = temp_reporting.list_arbitrage_proposals()
    assert proposals

    execution = ArbitrageExecutionResult(
        exec_id="exec",
        proposal_id="test",
        mode="dry",
        status="FILLED",
        started_at=0.0,
        completed_at=1.0,
        pnl_usd=1.0,
        fees_usd=0.0,
        message="ok",
    )
    temp_reporting.record_arbitrage_execution(execution, auto_trigger=False)
    execs = temp_reporting.list_arbitrage_executions()
    assert execs
