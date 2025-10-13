import pytest

pytest.importorskip("flask", reason="Flask not available in offline/proxy env")

from app.core.state import get_state, reset_state
from app.services.telegram.bot import (
    arbitrage_filters_summary,
    arbitrage_overview,
    build_status_report,
    set_arbitrage_auto,
    update_arb_setting,
    update_arbitrage_filter,
    update_scalp_setting,
)


def setup_function(_):
    reset_state()


def teardown_function(_):
    reset_state()


def test_build_status_report_contains_flags():
    text = build_status_report()
    assert "Auto mode" in text


def test_update_scalp_and_arb_settings():
    update_scalp_setting("tp", 0.5)
    update_arb_setting("interval", 45)
    state = get_state()
    assert state["scalp"]["tp_pct"] == 0.5
    assert state["arb"]["interval"] == 45


def test_arbitrage_filters_helpers():
    update_arbitrage_filter("minroi", 1.2)
    summary = arbitrage_filters_summary()
    assert "1.20" in summary
    overview = arbitrage_overview(limit=1)
    assert "filters" in overview
    set_arbitrage_auto(True)
    state = get_state()
    assert state["arb"]["auto_mode"] is True
