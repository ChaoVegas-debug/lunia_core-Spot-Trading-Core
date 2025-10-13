import importlib

import pytest

pytest.importorskip("flask", reason="Flask not available in offline/proxy env")

from app.core.state import reset_state
from app.services.telegram import bot as bot_module


def setup_function(_):
    reset_state()


def teardown_function(_):
    reset_state()


def test_equity_chart_generates_png(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_URL", f"sqlite:///{tmp_path/'chart.db'}")
    import app.db.reporting as reporting

    reporting = importlib.reload(reporting)
    reporting.record_trade(
        timestamp="2024-01-01T00:00:00",
        symbol="BTCUSDT",
        side="BUY",
        qty=0.1,
        price=20000,
        pnl=0.0,
    )
    reporting.record_trade(
        timestamp="2024-01-01T01:00:00",
        symbol="BTCUSDT",
        side="SELL",
        qty=0.1,
        price=21000,
        pnl=100.0,
    )
    monkeypatch.setattr(bot_module, "equity_curve", reporting.equity_curve)
    img = bot_module.equity_chart("day")
    assert isinstance(img, (bytes, bytearray))
    assert len(img) > 0
