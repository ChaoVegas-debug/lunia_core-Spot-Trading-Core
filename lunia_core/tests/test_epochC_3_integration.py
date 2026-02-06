"""
Test Epoch C.3 — Integration Tests

End-to-end lifecycle management tests.
"""
import pytest

from lunia_core.app.services.lifecycle.lifecycle_manager import LifecycleManager
from lunia_core.app.services.lifecycle.models import AllocationPolicy, VolatilityRegime
from lunia_core.app.services.risk_governor.models import PortfolioSnapshot, Position


def test_full_lifecycle():
    """Full lifecycle: size calculation → exit plan creation → exit trigger"""
    manager = LifecycleManager(policy=AllocationPolicy(base_unit_pct=0.01))
    
    # 1. Calculate entry size
    qty = manager.calculate_entry_size(
        total_equity=100000.0,
        strategy_confidence=0.75,
        volatility_regime=VolatilityRegime.NORMAL,
        reference_price=50000.0,
    )
    
    assert qty is not None
    assert qty > 0
    
    # 2. Create exit plan on fill
    plan = manager.on_fill(
        position_id="pos1",
        symbol="BTCUSDT",
        side="LONG",
        entry_price=50000.0,
        quantity=qty,
        strategy_type="TREND",
        atr=1000.0,
        now_ms=1000,
    )
    
    assert plan.symbol == "BTCUSDT"
    assert plan.stop_loss_price == 47000.0  # 50k - 3*ATR
    assert manager.get_active_plan("BTCUSDT") is not None
    
    # 3. Monitor exits (no trigger yet)
    snapshot = PortfolioSnapshot(
        as_of_ms=2000,
        total_equity=100000.0,
        positions=[
            Position(
                symbol="BTCUSDT",
                side="LONG",
                quantity=qty,
                avg_entry_price=50000.0,
                mark_price=51000.0,
                notional=qty * 51000.0,
            )
        ],
        prices={"BTCUSDT": 51000.0},
        pending=[],
    )
    
    exits = manager.on_tick(snapshot=snapshot, now_ms=2000)
    assert len(exits) == 0  # No exit yet
    
    # 4. SL hits → exit intent generated
    snapshot_sl_hit = PortfolioSnapshot(
        as_of_ms=3000,
        total_equity=100000.0,
        positions=[
            Position(
                symbol="BTCUSDT",
                side="LONG",
                quantity=qty,
                avg_entry_price=50000.0,
                mark_price=46000.0,
                notional=qty * 46000.0,
            )
        ],
        prices={"BTCUSDT": 46000.0},
        pending=[],
    )
    
    exits = manager.on_tick(snapshot=snapshot_sl_hit, now_ms=3000)
    
    assert len(exits) == 1
    assert exits[0].symbol == "BTCUSDT"
    assert exits[0].side == "SELL"
    assert exits[0].reason == "STOP_LOSS"
    assert exits[0].reduce_only is True


def test_multiple_positions():
    """Manage multiple positions simultaneously"""
    manager = LifecycleManager()
    
    # Create two positions
    plan1 = manager.on_fill(
        position_id="pos1",
        symbol="BTCUSDT",
        side="LONG",
        entry_price=50000.0,
        quantity=0.5,
        strategy_type="TREND",
        atr=1000.0,
        now_ms=1000,
    )
    
    plan2 = manager.on_fill(
        position_id="pos2",
        symbol="ETHUSDT",
        side="SHORT",
        entry_price=3000.0,
        quantity=5.0,
        strategy_type="MEAN_REVERSION",
        atr=50.0,
        now_ms=1000,
    )
    
    assert len(manager.get_all_plans()) == 2
    
    # Tick with both active
    snapshot = PortfolioSnapshot(
        as_of_ms=2000,
        total_equity=100000.0,
        positions=[
            Position(
                symbol="BTCUSDT",
                side="LONG",
                quantity=0.5,
                avg_entry_price=50000.0,
                mark_price=51000.0,
                notional=0.5 * 51000.0,
            ),
            Position(
                symbol="ETHUSDT",
                side="SHORT",
                quantity=5.0,
                avg_entry_price=3000.0,
                mark_price=2900.0,
                notional=5.0 * 2900.0,
            ),
        ],
        prices={"BTCUSDT": 51000.0, "ETHUSDT": 2900.0},
        pending=[],
    )
    
    # ETH should TP (SHORT TP at 2900)
    exits = manager.on_tick(snapshot=snapshot, now_ms=2000)
    
    assert len(exits) == 1
    assert exits[0].symbol == "ETHUSDT"
    assert exits[0].reason == "TAKE_PROFIT"


def test_position_cleanup():
    """Remove exit plan after position closes"""
    manager = LifecycleManager()
    
    manager.on_fill(
        position_id="pos1",
        symbol="BTCUSDT",
        side="LONG",
        entry_price=50000.0,
        quantity=0.5,
        strategy_type="TREND",
        atr=1000.0,
        now_ms=1000,
    )
    
    assert "BTCUSDT" in manager.get_all_plans()
    
    manager.remove_plan("BTCUSDT")
    
    assert "BTCUSDT" not in manager.get_all_plans()


def test_deterministic_sizing():
    """Same inputs → same size across manager instances"""
    policy = AllocationPolicy(base_unit_pct=0.01, max_scale_factor=2.5)
    
    manager1 = LifecycleManager(policy=policy)
    manager2 = LifecycleManager(policy=policy)
    
    qty1 = manager1.calculate_entry_size(
        100000.0, 0.75, VolatilityRegime.HIGH, 50000.0
    )
    
    qty2 = manager2.calculate_entry_size(
        100000.0, 0.75, VolatilityRegime.HIGH, 50000.0
    )
    
    assert qty1 == qty2


def test_fail_closed_missing_atr():
    """Missing ATR → exit plan creation fails"""
    manager = LifecycleManager()
    
    with pytest.raises(ValueError, match="ATR required"):
        manager.on_fill(
            position_id="pos1",
            symbol="BTCUSDT",
            side="LONG",
            entry_price=50000.0,
            quantity=0.5,
            strategy_type="TREND",
            atr=None,  # Missing!
            now_ms=1000,
        )
