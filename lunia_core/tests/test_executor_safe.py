import math

import pytest

from app.core.portfolio.portfolio import Portfolio
from app.core.risk.manager import RiskManager
from app.services.arbitrage.executor_safe import SafeArbitrageExecutor
from app.services.arbitrage.scanner import ArbitrageOpportunity


def make_opportunity(net_roi: float = 1.0, net_profit: float = 1.0) -> ArbitrageOpportunity:
    return ArbitrageOpportunity(
        proposal_id="test",
        symbol="BTCUSDT",
        buy_exchange="binance",
        sell_exchange="okx",
        buy_price=100.0,
        sell_price=101.0,
        gross_spread_pct=net_roi + 0.5,
        fees_total_pct=0.5,
        slippage_est_pct=0.1,
        net_roi_pct=net_roi,
        net_profit_usd=net_profit,
        qty_usd=100.0,
        created_at=0.0,
        transfer_type="internal",
        latency_ms=5.0,
        meta={"fees": {"transfer_fee_usd": 0.0}},
    )


def test_executor_dry_mode(tmp_path, monkeypatch):
    portfolio = Portfolio()
    executor = SafeArbitrageExecutor(portfolio=portfolio, risk=RiskManager(), admin_pin_hash="")
    opportunity = make_opportunity()
    result = executor.execute(opportunity, mode="dry")
    assert result.status == "FILLED"


def test_executor_requires_double_confirm():
    portfolio = Portfolio()
    executor = SafeArbitrageExecutor(portfolio=portfolio, risk=RiskManager(), admin_pin_hash="deadbeef")
    opportunity = make_opportunity()
    with pytest.raises(ValueError):
        executor.execute(opportunity, mode="real", double_confirm=False, pin=None)


def test_executor_rejects_negative_roi():
    portfolio = Portfolio()
    executor = SafeArbitrageExecutor(portfolio=portfolio, risk=RiskManager(), admin_pin_hash="")
    opportunity = make_opportunity(net_roi=-1.0, net_profit=-1.0)
    with pytest.raises(ValueError):
        executor.execute(opportunity)
