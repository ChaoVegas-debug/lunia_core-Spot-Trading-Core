import pytest

pytest.importorskip("flask", reason="Flask not available in offline/proxy env")

from app.services.telegram import bot


def test_capital_adjustment_and_spot_toggle():
    state = bot.set_capital_pct(0.2)
    assert state["ops"]["capital"]["cap_pct"] == 0.2
    state = bot.adjust_capital_pct(0.1)
    assert state["ops"]["capital"]["cap_pct"] == 0.3
    state = bot.toggle_spot(False)
    assert state["spot"]["enabled"] is False
    state = bot.update_strategy_weight("micro_trend_scalper", 0.7)
    assert state["spot"]["weights"]["micro_trend_scalper"] == 0.7
    status = bot.spot_status()
    assert status["cap_pct"] == state["ops"]["capital"]["cap_pct"]
