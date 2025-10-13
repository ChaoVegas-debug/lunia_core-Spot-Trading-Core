from app.core.risk.manager import RiskLimits, RiskManager


def test_exceeds_leverage():
    manager = RiskManager(RiskLimits(max_pos_leverage=2.0))
    ok, reason = manager.validate_order(equity_usd=1000, order_value_usd=100, leverage=3.0)
    assert not ok
    assert reason == "max leverage exceeded"


def test_exceeds_symbol_risk():
    manager = RiskManager(RiskLimits(max_symbol_risk_pct=0.5, max_daily_loss_pct=100.0))
    ok, reason = manager.validate_order(equity_usd=1000, order_value_usd=20, leverage=1.0)
    assert not ok
    assert reason == "max symbol risk exceeded"


def test_daily_loss_limit_blocks_orders():
    limits = RiskLimits(max_daily_loss_pct=2.0, max_symbol_risk_pct=100.0)
    manager = RiskManager(limits)
    manager.daily_pnl = -50.0
    ok, reason = manager.validate_order(equity_usd=1000, order_value_usd=10, leverage=1.0)
    assert not ok
    assert reason == "max daily loss exceeded"
