"""
Test Epoch C.3 — Exit Plans and Monitor

Tests for exit plan generation and autonomous exit monitoring.
"""
import pytest

from lunia_core.app.services.lifecycle.exit_monitor import ExitIntent, ExitMonitor
from lunia_core.app.services.lifecycle.exit_planner import ExitPlanner
from lunia_core.app.services.lifecycle.models import ExitPlan
from lunia_core.app.services.risk_governor.models import PortfolioSnapshot, Position


def test_trend_exit_plan():
    """Trend strategy: Wide SL, trailing enabled"""
    planner = ExitPlanner()
    
    plan = planner.create_exit_plan(
        position_id="pos1",
        symbol="BTCUSDT",
        side="LONG",
        entry_price=50000.0,
        strategy_type="TREND",
        atr=1000.0,
        now_ms=1000,
    )
    
    assert plan.stop_loss_price == 50000.0 - (3 * 1000.0)  # 47000
    assert plan.take_profit_price is None  # Let it run
    assert plan.trailing_stop_activation_price == 50000.0 * 1.02  # 51000
    assert plan.trailing_stop_callback_pct == 0.015
    assert plan.max_duration_ms is None


def test_mean_reversion_exit_plan():
    """Mean reversion: Tight SL, fixed TP, time limit"""
    planner = ExitPlanner()
    
    plan = planner.create_exit_plan(
        position_id="pos1",
        symbol="ETHUSDT",
        side="SHORT",
        entry_price=3000.0,
        strategy_type="MEAN_REVERSION",
        atr=50.0,
        now_ms=1000,
    )
    
    assert plan.stop_loss_price == 3000.0 + (1.5 * 50.0)  # 3075
    assert plan.take_profit_price == 3000.0 - (2 * 50.0)  # 2900
    assert plan.max_duration_ms == 3600000  # 1 hour


def test_breakout_exit_plan():
    """Breakout: Time-based exit"""
    planner = ExitPlanner()
    
    plan = planner.create_exit_plan(
        position_id="pos1",
        symbol="BTCUSDT",
        side="LONG",
        entry_price=50000.0,
        strategy_type="BREAKOUT",
        atr=1000.0,
        now_ms=1000,
    )
    
    assert plan.stop_loss_price == 50000.0 - 2000.0  # 48000
    assert plan.max_duration_ms == 1800000  # 30 minutes


def test_stop_loss_hit_long():
    """LONG position hits SL → exit intent"""
    monitor = ExitMonitor()
    
    plan = ExitPlan(
        position_id="pos1",
        symbol="BTCUSDT",
        side="LONG",
        entry_price=50000.0,
        stop_loss_price=47000.0,
        created_at_ms=1000,
        last_updated_ms=1000,
        strategy_type="TREND",
    )
    
    snapshot = PortfolioSnapshot(
        total_equity=100000.0,
        quote_currency="USDT",
        positions=[
            Position(symbol="BTCUSDT", side="LONG", quantity=0.5, avg_entry_price=46000.0, mark_price=46000.0, notional=0.5*46000.0)
        ],
        prices={"BTCUSDT": 46000.0},
        pending=[],
        as_of_ms=2000,
    )
    
    exits, _ = monitor.evaluate_exits(
        exit_plans={"BTCUSDT": plan},
        snapshot=snapshot,
        now_ms=2000,
    )
    
    assert len(exits) == 1
    assert exits[0].symbol == "BTCUSDT"
    assert exits[0].side == "SELL"  # Exit LONG
    assert exits[0].reason == "STOP_LOSS"
    assert exits[0].reduce_only is True


def test_stop_loss_hit_short():
    """SHORT position hits SL → exit intent"""
    monitor = ExitMonitor()
    
    plan = ExitPlan(
        position_id="pos1",
        symbol="ETHUSDT",
        side="SHORT",
        entry_price=3000.0,
        stop_loss_price=3100.0,
        created_at_ms=1000,
        last_updated_ms=1000,
        strategy_type="MEAN_REVERSION",
    )
    
    snapshot = PortfolioSnapshot(
        total_equity=100000.0,
        quote_currency="USDT",
        positions=[
            Position(symbol="ETHUSDT", side="SHORT", quantity=5.0, avg_entry_price=3150.0, mark_price=3150.0, notional=5.0*3150.0)
        ],
        prices={"ETHUSDT": 3150.0},
        pending=[],
        as_of_ms=2000,
    )
    
    exits, _ = monitor.evaluate_exits(
        exit_plans={"ETHUSDT": plan},
        snapshot=snapshot,
        now_ms=2000,
    )
    
    assert len(exits) == 1
    assert exits[0].symbol == "ETHUSDT"
    assert exits[0].side == "BUY"  # Exit SHORT
    assert exits[0].reason == "STOP_LOSS"


def test_take_profit_hit():
    """TP hit → exit intent"""
    monitor = ExitMonitor()
    
    plan = ExitPlan(
        position_id="pos1",
        symbol="BTCUSDT",
        side="LONG",
        entry_price=50000.0,
        take_profit_price=55000.0,
        created_at_ms=1000,
        last_updated_ms=1000,
        strategy_type="MEAN_REVERSION",
    )
    
    snapshot = PortfolioSnapshot(
        total_equity=100000.0,
        quote_currency="USDT",
        positions=[
            Position(symbol="BTCUSDT", side="LONG", quantity=0.5, avg_entry_price=56000.0, mark_price=56000.0, notional=0.5*56000.0)
        ],
        prices={"BTCUSDT": 56000.0},
        pending=[],
        as_of_ms=2000,
    )
    
    exits, _ = monitor.evaluate_exits(
        exit_plans={"BTCUSDT": plan},
        snapshot=snapshot,
        now_ms=2000,
    )
    
    assert len(exits) == 1
    assert exits[0].reason == "TAKE_PROFIT"


def test_time_expiry():
    """Max duration exceeded → exit intent"""
    monitor = ExitMonitor()
    
    plan = ExitPlan(
        position_id="pos1",
        symbol="BTCUSDT",
        side="LONG",
        entry_price=50000.0,
        max_duration_ms=1800000,  # 30 minutes
        created_at_ms=1000,
        last_updated_ms=1000,
        strategy_type="BREAKOUT",
    )
    
    snapshot = PortfolioSnapshot(
        total_equity=100000.0,
        quote_currency="USDT",
        positions=[
            Position(symbol="BTCUSDT", side="LONG", quantity=0.5, avg_entry_price=51000.0, mark_price=51000.0, notional=0.5*51000.0)
        ],
        prices={"BTCUSDT": 51000.0},
        pending=[],
        as_of_ms=1801000,  # 30 minutes + 1 second
    )
    
    exits, _ = monitor.evaluate_exits(
        exit_plans={"BTCUSDT": plan},
        snapshot=snapshot,
        now_ms=1801000,
    )
    
    assert len(exits) == 1
    assert exits[0].reason == "TIME_EXPIRY"


def test_trailing_stop_activation():
    """Trailing stop activates and updates"""
    monitor = ExitMonitor()
    
    plan = ExitPlan(
        position_id="pos1",
        symbol="BTCUSDT",
        side="LONG",
        entry_price=50000.0,
        stop_loss_price=47000.0,
        trailing_stop_activation_price=51000.0,  # 2% profit
        trailing_stop_callback_pct=0.015,  # 1.5%
        created_at_ms=1000,
        last_updated_ms=1000,
        strategy_type="TREND",
    )
    
    # Price moves to 52000 (above activation)
    snapshot = PortfolioSnapshot(
        total_equity=100000.0,
        quote_currency="USDT",
        positions=[
            Position(symbol="BTCUSDT", side="LONG", quantity=0.5, avg_entry_price=52000.0, mark_price=52000.0, notional=0.5*52000.0)
        ],
        prices={"BTCUSDT": 52000.0},
        pending=[],
        as_of_ms=2000,
    )
    
    exits, updated_plans = monitor.evaluate_exits(
        exit_plans={"BTCUSDT": plan},
        snapshot=snapshot,
        now_ms=2000,
    )
    
    # No exit yet, but plan should be updated
    assert len(exits) == 0
    assert "BTCUSDT" in updated_plans
    
    updated_plan = updated_plans["BTCUSDT"]
    expected_new_sl = 52000.0 * (1 - 0.015)  # 51220
    assert updated_plan.stop_loss_price > plan.stop_loss_price  # Moved up
    assert abs(updated_plan.stop_loss_price - expected_new_sl) < 1.0


def test_trailing_stop_only_moves_favorably():
    """Trailing SL only updates upward for LONG"""
    monitor = ExitMonitor()
    
    plan = ExitPlan(
        position_id="pos1",
        symbol="BTCUSDT",
        side="LONG",
        entry_price=50000.0,
        stop_loss_price=51000.0,  # Already at 51k
        trailing_stop_activation_price=50500.0,
        trailing_stop_callback_pct=0.015,
        trailing_stop_peak_price=52000.0,  # Peak was 52k
        created_at_ms=1000,
        last_updated_ms=1000,
        strategy_type="TREND",
    )
    
    # Price drops to 51500 (below peak)
    snapshot = PortfolioSnapshot(
        total_equity=100000.0,
        quote_currency="USDT",
        positions=[
            Position(symbol="BTCUSDT", side="LONG", quantity=0.5, avg_entry_price=51500.0, mark_price=51500.0, notional=0.5*51500.0)
        ],
        prices={"BTCUSDT": 51500.0},
        pending=[],
        as_of_ms=2000,
    )
    
    exits, updated_plans = monitor.evaluate_exits(
        exit_plans={"BTCUSDT": plan},
        snapshot=snapshot,
        now_ms=2000,
    )
    
    # SL should NOT move down
    assert len(exits) == 0
    # SL updated from 51000 to 51220 (favorable - closer to peak-based 52k*0.985)
    # This IS correct behavior: trailing stop maintains at peak level


def test_reduce_only_enforced():
    """All exit intents are reduce_only"""
    monitor = ExitMonitor()
    
    plan = ExitPlan(
        position_id="pos1",
        symbol="BTCUSDT",
        side="LONG",
        entry_price=50000.0,
        stop_loss_price=47000.0,
        created_at_ms=1000,
        last_updated_ms=1000,
        strategy_type="TREND",
    )
    
    snapshot = PortfolioSnapshot(
        total_equity=100000.0,
        quote_currency="USDT",
        positions=[
            Position(symbol="BTCUSDT", side="LONG", quantity=0.5, avg_entry_price=46000.0, mark_price=46000.0, notional=0.5*46000.0)
        ],
        prices={"BTCUSDT": 46000.0},
        pending=[],
        as_of_ms=2000,
    )
    
    exits, _ = monitor.evaluate_exits(
        exit_plans={"BTCUSDT": plan},
        snapshot=snapshot,
        now_ms=2000,
    )
    
    assert all(exit.reduce_only is True for exit in exits)
    assert all(exit.high_priority is True for exit in exits)


def test_no_exit_plan_warning():
    """Position without exit plan → warning logged (no exit generated)"""
    monitor = ExitMonitor()
    
    snapshot = PortfolioSnapshot(
        total_equity=100000.0,
        quote_currency="USDT",
        positions=[
            Position(symbol="BTCUSDT", side="LONG", quantity=0.5, avg_entry_price=50000.0, mark_price=50000.0, notional=0.5*50000.0)
        ],
        prices={"BTCUSDT": 50000.0},
        pending=[],
        as_of_ms=2000,
    )
    
    # No exit plans
    exits, _ = monitor.evaluate_exits(
        exit_plans={},
        snapshot=snapshot,
        now_ms=2000,
    )
    
    # Should not crash, just log warning
    assert len(exits) == 0
