import json

import pytest

from app.core.arbitrage.executor import ArbitrageExecutor
from app.core.portfolio.portfolio import Portfolio
from app.core.risk.manager import RiskLimits, RiskManager


@pytest.fixture
def opportunity():
    return {
        "symbol": "BTCUSDT",
        "buy_ex": "binance",
        "sell_ex": "okx",
        "buy_px": 100.0,
        "sell_px": 101.0,
        "ts": 1_700_000_000.0,
    }


def test_arbitrage_executor_simulation_pnl(monkeypatch, opportunity):
    monkeypatch.setenv("ARB_FEE_PCT", "0")
    monkeypatch.setenv("ARB_SLIPPAGE_PCT", "0")
    executor = ArbitrageExecutor(Portfolio(), RiskManager(), mode="simulation", default_equity_usd=1_000_000)
    result = executor.execute(opportunity, qty_usd=100.0)
    assert result.status == "FILLED"
    assert pytest.approx(result.pnl, rel=1e-6) == 1.0
    assert pytest.approx(executor.total_pnl, rel=1e-6) == 1.0


def test_arbitrage_executor_risk_reject(monkeypatch, opportunity):
    monkeypatch.setenv("ARB_FEE_PCT", "0")
    monkeypatch.setenv("ARB_SLIPPAGE_PCT", "0")
    limits = RiskLimits()
    limits.max_symbol_risk_pct = 0.1
    risk = RiskManager(limits=limits)
    executor = ArbitrageExecutor(Portfolio(), risk, mode="simulation", default_equity_usd=1_000)
    result = executor.execute(opportunity, qty_usd=500.0)
    assert result.status == "REJECTED"
    assert "max symbol risk" in result.reason


def test_arbitrage_executor_mock_writes_trades(tmp_path, monkeypatch, opportunity):
    monkeypatch.setenv("ARB_FEE_PCT", "0")
    monkeypatch.setenv("ARB_SLIPPAGE_PCT", "0")
    trade_log = tmp_path / "trades.jsonl"
    import app.core.arbitrage.executor as executor_module

    monkeypatch.setattr(executor_module, "TRADES_LOG_PATH", trade_log)
    portfolio = Portfolio()
    executor = ArbitrageExecutor(portfolio, RiskManager(), mode="mock", default_equity_usd=1_000_000)
    result = executor.execute(opportunity, qty_usd=100.0)
    assert result.status == "FILLED"
    assert trade_log.exists()
    lines = trade_log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    events = [json.loads(line) for line in lines]
    assert {event["side"] for event in events} == {"BUY", "SELL"}
    position = portfolio.get_position("BTCUSDT")
    assert position is not None
    assert position.quantity == 0
