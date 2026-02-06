"""
Test Epoch C.4 — Recovery & Persistent Manager

Tests for crash recovery, orphan handling, and idempotency deduplication.
"""
import pytest
import tempfile
import os
import time

from lunia_core.app.services.state_store import SQLiteStateStore, PersistedExitPlanState
from lunia_core.app.services.lifecycle.lifecycle_recovery import LifecycleRecovery
from lunia_core.app.services.lifecycle.persistent_lifecycle_manager import PersistentLifecycleManager
from lunia_core.app.services.lifecycle.exit_planner import ExitPlanner
from lunia_core.app.services.lifecycle.models import AllocationPolicy, VolatilityRegime, ExitPlan
from lunia_core.app.services.risk_governor.models import PortfolioSnapshot, Position


@pytest.fixture
def temp_db():
    """Create temporary database."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def store(temp_db):
    """Create initialized store."""
    s = SQLiteStateStore(temp_db)
    s.init()
    return s


@pytest.fixture
def recovery(store):
    """Create recovery manager."""
    planner = ExitPlanner()
    return LifecycleRecovery(store, planner)


@pytest.fixture
def persistent_manager(store):
    """Create persistent lifecycle manager."""
    return PersistentLifecycleManager(store)


def test_orphan_recovery(recovery, store):
    """Orphan position gets emergency plan."""
    # Snapshot has position, DB has no plan
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
                notional=25500.0,
            )
        ],
        prices={"BTCUSDT": 51000.0},
        pending=[],
    )
    
    registry = recovery.restore(snapshot, now_ms=2000)
    
    # Should have created emergency plan
    assert "BTCUSDT" in registry.active_positions
    state = registry.active_positions["BTCUSDT"]
    assert state.status == "RECOVERED_ORPHAN"
    assert state.exit_plan.strategy_type == "EMERGENCY_RECOVERY"
    # Tight SL (0.5%)
    assert abs(state.exit_plan.stop_loss_price - 50000.0 * 0.995) < 10


def test_ghost_cleanup(recovery, store):
    """Ghost plan (no position) gets marked CLOSED_EXTERNALLY."""
    # Add orphan plan in DB
    exit_plan = ExitPlan(
        position_id="pos1",
        symbol="ETHUSDT",
        side="SHORT",
        entry_price=3000.0,
        stop_loss_price=3100.0,
        created_at_ms=1000,
        last_updated_ms=1000,
        strategy_type="MEAN_REVERSION",
    )
    
    state = PersistedExitPlanState(
        version=1,
        position_id="pos1",
        symbol="ETHUSDT",
        side="SHORT",
        entry_price=3000.0,
        quantity=5.0,
        exit_plan=exit_plan,
        trailing_peak_price=None,
        trailing_active=False,
        created_at_ms=1000,
        last_updated_ms=1000,
        status="ACTIVE",
    )
    
    store.upsert_exit_plan(state)
    
    # Snapshot has NO position
    snapshot = PortfolioSnapshot(
        as_of_ms=2000,
        total_equity=100000.0,
        positions=[],
        prices={},
        pending=[],
    )
    
    registry = recovery.restore(snapshot, now_ms=2000)
    
    # Should have NO active positions
    assert len(registry.active_positions) == 0
    
    # Check DB marked closed
    active = store.list_active(as_of_ms=3000)
    assert len(active) == 0


def test_normal_recovery(recovery, store):
    """Normal case: position and plan match."""
    # Add plan in DB
    exit_plan = ExitPlan(
        position_id="pos1",
        symbol="BTCUSDT",
        side="LONG",
        entry_price=50000.0,
        stop_loss_price=47000.0,
        created_at_ms=1000,
        last_updated_ms=1000,
        strategy_type="TREND",
    )
    
    state = PersistedExitPlanState(
        version=1,
        position_id="pos1",
        symbol="BTCUSDT",
        side="LONG",
        entry_price=50000.0,
        quantity=0.5,
        exit_plan=exit_plan,
        trailing_peak_price=None,
        trailing_active=False,
        created_at_ms=1000,
        last_updated_ms=1000,
        status="ACTIVE",
    )
    
    store.upsert_exit_plan(state)
    
    # Snapshot has matching position
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
                notional=25500.0,
            )
        ],
        prices={"BTCUSDT": 51000.0},
        pending=[],
    )
    
    registry = recovery.restore(snapshot, now_ms=2000)
    
    # Should have 1 active position
    assert len(registry.active_positions) == 1
    assert "BTCUSDT" in registry.active_positions


def test_persistent_manager_on_fill(persistent_manager):
    """on_fill persists exit plan."""
    plan = persistent_manager.on_fill(
        position_id="pos1",
        symbol="BTCUSDT",
        side="LONG",
        entry_price=50000.0,
        quantity=0.5,
        strategy_type="TREND",
        atr=1000.0,
        now_ms=1000,
    )
    
    assert plan.symbol == "BTCUSDT"
    
    # Check persisted
    active = persistent_manager.store.list_active(as_of_ms=2000)
    assert len(active) == 1
    assert active[0].symbol == "BTCUSDT"


def test_persistent_manager_idempotency(persistent_manager):
    """Duplicate exit intents are dropped."""
    # Create position
    persistent_manager.on_fill(
        position_id="pos1",
        symbol="BTCUSDT",
        side="LONG",
        entry_price=50000.0,
        quantity=0.5,
        strategy_type="TREND",
        atr=1000.0,
        now_ms=1000,
    )
    
    # Trigger SL (twice)
    snapshot = PortfolioSnapshot(
        as_of_ms=2000,
        total_equity=100000.0,
        positions=[
            Position(
                symbol="BTCUSDT",
                side="LONG",
                quantity=0.5,
                avg_entry_price=50000.0,
                mark_price=46000.0,
                notional=23000.0,
            )
        ],
        prices={"BTCUSDT": 46000.0},
        pending=[],
    )
    
    # First call
    intents1 = persistent_manager.on_tick(snapshot, now_ms=2000)
    assert len(intents1) == 1
    
    # Second call (same tick, same price)
    intents2 = persistent_manager.on_tick(snapshot, now_ms=2000)
    assert len(intents2) == 0  # Dropped due to idempotency


def test_persistent_manager_restore(persistent_manager):
    """restore_from_crash rebuilds state."""
    # Add plan to DB
    exit_plan = ExitPlan(
        position_id="pos1",
        symbol="BTCUSDT",
        side="LONG",
        entry_price=50000.0,
        stop_loss_price=47000.0,
        created_at_ms=1000,
        last_updated_ms=1000,
        strategy_type="TREND",
    )
    
    state = PersistedExitPlanState(
        version=1,
        position_id="pos1",
        symbol="BTCUSDT",
        side="LONG",
        entry_price=50000.0,
        quantity=0.5,
        exit_plan=exit_plan,
        trailing_peak_price=None,
        trailing_active=False,
        created_at_ms=1000,
        last_updated_ms=1000,
        status="ACTIVE",
    )
    
    persistent_manager.store.upsert_exit_plan(state)
    
    # Snapshot has matching position
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
                notional=25500.0,
            )
        ],
        prices={"BTCUSDT": 51000.0},
        pending=[],
    )
    
    persistent_manager.restore_from_crash(snapshot, now_ms=2000)
    
    # Check inner manager has plan
    assert persistent_manager.get_active_plan("BTCUSDT") is not None


def test_persistent_manager_purge(persistent_manager):
    """purge_expired_keys removes old idempotency keys."""
    # Reserve key
    key = "EXIT:pos1:STOP_LOSS:5000000:1738762890"
    persistent_manager.store.reserve_idempotency(
        key, "hash1", 1000, 1000  # 1ms TTL
    )
    
    # Purge after expiry
    purged = persistent_manager.purge_expired_keys(now_ms=5000)
    
    assert purged >= 1


def test_persistent_manager_on_exit_executed(persistent_manager):
    """on_exit_executed commits idempotency."""
    # Reserve key
    key = "EXIT:pos1:STOP_LOSS:5000000:1738762890"
    persistent_manager.store.reserve_idempotency(
        key, "hash1", 1000, 86400000
    )
    
    # Commit
    persistent_manager.on_exit_executed("pos1", key, 2000)
    
    # Check status
    cursor = persistent_manager.store.conn.execute(
        "SELECT status FROM idempotency_keys WHERE key = ?", (key,)
    )
    row = cursor.fetchone()
    assert row[0] == "COMMITTED"


def test_multiple_orphans(recovery, store):
    """Multiple orphans all get emergency plans."""
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
                notional=25500.0,
            ),
            Position(
                symbol="ETHUSDT",
                side="SHORT",
                quantity=5.0,
                avg_entry_price=3000.0,
                mark_price=2900.0,
                notional=14500.0,
            ),
        ],
        prices={"BTCUSDT": 51000.0, "ETHUSDT": 2900.0},
        pending=[],
    )
    
    registry = recovery.restore(snapshot, now_ms=2000)
    
    assert len(registry.active_positions) == 2
    assert all(
        p.status == "RECOVERED_ORPHAN"
        for p in registry.active_positions.values()
    )


def test_deterministic_sizing(persistent_manager):
    """calculate_entry_size is deterministic."""
    qty1 = persistent_manager.calculate_entry_size(
        100000.0, 0.75, VolatilityRegime.NORMAL, 50000.0
    )
    
    qty2 = persistent_manager.calculate_entry_size(
        100000.0, 0.75, VolatilityRegime.NORMAL, 50000.0
    )
    
    assert qty1 == qty2
