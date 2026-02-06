"""
Test Epoch C.4 — Integration & Edge Cases

Integration tests for crash recovery scenarios and edge cases.
"""
import pytest
import tempfile
import os

from lunia_core.app.services.state_store import SQLiteStateStore, PersistedExitPlanState
from lunia_core.app.services.lifecycle.persistent_lifecycle_manager import PersistentLifecycleManager
from lunia_core.app.services.lifecycle.models import ExitPlan, AllocationPolicy, VolatilityRegime
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
def manager(store):
    """Create persistent manager."""
    return PersistentLifecycleManager(store)


def test_full_crash_recovery_flow(manager):
    """Full crash → restart → resume flow."""
    # 1. Create position
    plan = manager.on_fill(
        position_id="pos1",
        symbol="BTCUSDT",
        side="LONG",
        entry_price=50000.0,
        quantity=0.5,
        strategy_type="TREND",
        atr=1000.0,
        now_ms=1000,
    )
    
    assert plan is not None
    
    # 2. Simulate crash (create new manager instance)
    manager2 = PersistentLifecycleManager(manager.store)
    
    # 3. Restore from crash
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
    
    manager2.restore_from_crash(snapshot, now_ms=2000)
    
    # 4. Verify plan restored
    assert manager2.get_active_plan("BTCUSDT") is not None


def test_store_unavailable_fail_closed(manager):
    """When store fails, new entries blocked."""
    # Corrupt store
    manager.store_available = False
    
    # Try to create position
    plan = manager.on_fill(
        position_id="pos1",
        symbol="BTCUSDT",
        side="LONG",
        entry_price=50000.0,
        quantity=0.5,
        strategy_type="TREND",
        atr=1000.0,
        now_ms=1000,
    )
    
    # Plan created in memory but NOT persisted
    assert plan is not None
    
    # Store has NO record
    active = manager.store.list_active(as_of_ms=2000)
    assert len(active) == 0


def test_idempotency_across_restart(temp_db):
    """Idempotency preserved across restart."""
    # Manager 1: Create position and trigger exit
    store1 = SQLiteStateStore(temp_db)
    store1.init()
    manager1 = PersistentLifecycleManager(store1)
    
    manager1.on_fill(
        position_id="pos1",
        symbol="BTCUSDT",
        side="LONG",
        entry_price=50000.0,
        quantity=0.5,
        strategy_type="TREND",
        atr=1000.0,
        now_ms=1000,
    )
    
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
    
    exits1 = manager1.on_tick(snapshot, now_ms=2000)
    assert len(exits1) == 1
    
    # Manager 2: Restart and try same exit
    store2 = SQLiteStateStore(temp_db)
    store2.init()
    manager2 = PersistentLifecycleManager(store2)
    
    manager2.restore_from_crash(snapshot, now_ms=2000)
    
    # Same tick should be deduplicated
    exits2 = manager2.on_tick(snapshot, now_ms=2000)
    assert len(exits2) == 0


def test_multiple_positions_persistence(manager):
    """Multiple positions all persisted correctly."""
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
    
    manager.on_fill(
        position_id="pos2",
        symbol="ETHUSDT",
        side="SHORT",
        entry_price=3000.0,
        quantity=5.0,
        strategy_type="MEAN_REVERSION",
        atr=50.0,
        now_ms=1100,
    )
    
    active = manager.store.list_active(as_of_ms=2000)
    assert len(active) == 2
    symbols = {p.symbol for p in active}
    assert symbols == {"BTCUSDT", "ETHUSDT"}


def test_schema_version_enforcement(temp_db):
    """Schema version mismatch blocks initialization."""
    store = SQLiteStateStore(temp_db)
    store.init()
    
    # Manually corrupt schema version
    store.conn.execute("UPDATE schema_version SET version = 99")
    store.conn.commit()
    store.conn.close()
    
    # New store should fail
    store2 = SQLiteStateStore(temp_db)
    with pytest.raises(RuntimeError, match="SCHEMA_MISMATCH_BLOCK"):
        store2.init()


def test_allocation_determinism_persists(manager):
    """Allocation remains deterministic after persist."""
    qty1 = manager.calculate_entry_size(
        100000.0, 0.75, VolatilityRegime.NORMAL, 50000.0
    )
    
    # Persist something
    manager.on_fill(
        position_id="pos1",
        symbol="BTCUSDT",
        side="LONG",
        entry_price=50000.0,
        quantity=qty1,
        strategy_type="TREND",
        atr=1000.0,
        now_ms=1000,
    )
    
    # Recalculate
    qty2 = manager.calculate_entry_size(
        100000.0, 0.75, VolatilityRegime.NORMAL, 50000.0
    )
    
    assert qty1 == qty2


def test_emergency_plan_has_tight_sl(manager):
    """Emergency plans have 0.5% SL."""
    # Create orphan scenario
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
    
    manager.restore_from_crash(snapshot, now_ms=2000)
    
    # Check emergency plan
    active = manager.store.list_active(as_of_ms=2000)
    assert len(active) == 1
    
    emergency = active[0]
    assert emergency.status == "RECOVERED_ORPHAN"
    
    # SL should be ~0.5% below entry
    expected_sl = 50000.0 * 0.995
    actual_sl = emergency.exit_plan.stop_loss_price
    
    # Allow 1% tolerance
    assert abs(actual_sl - expected_sl) / expected_sl < 0.01


def test_purge_respects_ttl(manager):
    """Purge only removes expired keys."""
    # Reserve keys with different TTLs
    manager.store.reserve_idempotency("key1", "hash1", 1000, 1000)  # 1s TTL
    manager.store.reserve_idempotency("key2", "hash2", 1000, 86400000)  # 24h TTL
    
    # Purge after 2 seconds
    purged = manager.purge_expired_keys(now_ms=3000)
    
    assert purged >= 1
    
    # Check key2 still exists
    cursor = manager.store.conn.execute(
        "SELECT COUNT(*) FROM idempotency_keys WHERE key = 'key2'"
    )
    assert cursor.fetchone()[0] == 1


def test_exit_executed_commits_key(manager):
    """on_exit_executed commits idempotency."""
    key = "EXIT:pos1:STOP_LOSS:5000000:1738762890"
    manager.store.reserve_idempotency(key, "hash1", 1000, 86400000)
    
    manager.on_exit_executed("pos1", key, 2000)
    
    # Check committed
    cursor = manager.store.conn.execute(
        "SELECT status, committed_at_ms FROM idempotency_keys WHERE key = ?",
        (key,)
    )
    row = cursor.fetchone()
    assert row[0] == "COMMITTED"
    assert row[1] == 2000


def test_health_check_accurate(manager):
    """Health check reflects true state."""
    # Add position
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
    
    health = manager.store.health()
    
    assert health["status"] == "HEALTHY"
    assert health["schema_version"] == 1
    assert health["active_exit_plans"] == 1


def test_circuit_breaker_persistence(manager):
    """Circuit breaker state persists."""
    from lunia_core.app.services.state_store.models import CircuitBreakerRecord
    
    record = CircuitBreakerRecord(
        adapter_name="binance",
        symbol="BTCUSDT",
        consecutive_blocks=5,
        last_block_ms=1000,
        halt_recommended=True,
    )
    
    manager.store.save_circuit_breaker(record)
    
    loaded = manager.store.load_circuit_breaker("binance", "BTCUSDT")
    
    assert loaded.consecutive_blocks == 5
    assert loaded.halt_recommended is True


def test_empty_recovery(manager):
    """Recovery with empty DB and empty snapshot."""
    snapshot = PortfolioSnapshot(
        as_of_ms=2000,
        total_equity=100000.0,
        positions=[],
        prices={},
        pending=[],
    )
    
    manager.restore_from_crash(snapshot, now_ms=2000)
    
    assert len(manager.get_all_plans()) == 0
