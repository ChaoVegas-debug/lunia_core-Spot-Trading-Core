"""
Test Epoch C.4 — State Store

Tests for SQLite state store with schema governance, CRUD, and idempotency.
"""
import pytest
import tempfile
import os

from lunia_core.app.services.state_store import SQLiteStateStore, PersistedExitPlanState, IdempotencyRecord, CircuitBreakerRecord
from lunia_core.app.services.lifecycle.models import ExitPlan


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
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


def test_schema_creation(temp_db):
    """Schema initialization creates all tables."""
    store = SQLiteStateStore(temp_db)
    store.init()
    
    # Check tables exist
    cursor = store.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
    tables = {row[0] for row in cursor.fetchall()}
    
    assert "schema_version" in tables
    assert "exit_plan_states" in tables
    assert "idempotency_keys" in tables
    assert "circuit_breaker_states" in tables


def test_schema_version_validation(temp_db):
    """Schema mismatch raises RuntimeError."""
    store = SQLiteStateStore(temp_db)
    store.init()
    
    # Manually change schema version
    store.conn.execute("UPDATE schema_version SET version = 99")
    store.conn.commit()
    store.conn.close()
    
    # Attempt to init again
    store2 = SQLiteStateStore(temp_db)
    with pytest.raises(RuntimeError, match="SCHEMA_MISMATCH_BLOCK"):
        store2.init()


def test_upsert_exit_plan(store):
    """Upsert creates and updates exit plans."""
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
    
    # Load back
    loaded = store.list_active(as_of_ms=2000)
    assert len(loaded) == 1
    assert loaded[0].position_id == "pos1"
    assert loaded[0].symbol == "BTCUSDT"


def test_mark_closed(store):
    """mark_closed updates status."""
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
    store.mark_closed("pos1", "EXIT_EXECUTED", 3000)
    
    # Should not appear in active list
    active = store.list_active(as_of_ms=4000)
    assert len(active) == 0


def test_idempotency_reserve(store):
    """reserve_idempotency returns True for new keys, False for existing."""
    key = "EXIT:pos1:STOP_LOSS:5000000:1738762890"
    payload_hash = "abc123"
    now_ms = 1000
    ttl_ms = 86400000
    
    # First reserve
    reserved1 = store.reserve_idempotency(key, payload_hash, now_ms, ttl_ms)
    assert reserved1 is True
    
    # Second reserve (duplicate)
    reserved2 = store.reserve_idempotency(key, payload_hash, now_ms, ttl_ms)
    assert reserved2 is False


def test_idempotency_commit(store):
    """commit_idempotency updates status."""
    key = "EXIT:pos1:STOP_LOSS:5000000:1738762890"
    payload_hash = "abc123"
    now_ms = 1000
    ttl_ms = 86400000
    
    store.reserve_idempotency(key, payload_hash, now_ms, ttl_ms)
    store.commit_idempotency(key, now_ms + 100)
    
    # Check status
    cursor = store.conn.execute(
        "SELECT status FROM idempotency_keys WHERE key = ?", (key,)
    )
    row = cursor.fetchone()
    assert row[0] == "COMMITTED"


def test_idempotency_purge(store):
    """purge_idempotency removes expired keys."""
    # Add expired key
    key1 = "EXIT:pos1:STOP_LOSS:5000000:1738762890"
    store.reserve_idempotency(key1, "hash1", 1000, 1000)  # 1 second TTL
    
    # Add fresh key
    key2 = "EXIT:pos2:TAKE_PROFIT:5100000:1738762891"
    store.reserve_idempotency(key2, "hash2", 10000, 86400000)  # 24h TTL
    
    # Purge after 5 seconds
    purged = store.purge_idempotency(now_ms=5000)
    
    assert purged == 1
    
    # Check key1 removed
    cursor = store.conn.execute(
        "SELECT COUNT(*) FROM idempotency_keys WHERE key = ?", (key1,)
    )
    assert cursor.fetchone()[0] == 0
    
    # Check key2 still exists
    cursor = store.conn.execute(
        "SELECT COUNT(*) FROM idempotency_keys WHERE key = ?", (key2,)
    )
    assert cursor.fetchone()[0] == 1


def test_circuit_breaker_save_load(store):
    """save_circuit_breaker and load work correctly."""
    record = CircuitBreakerRecord(
        adapter_name="binance",
        symbol="BTCUSDT",
        consecutive_blocks=3,
        last_block_ms=1000,
        halt_recommended=True,
    )
    
    store.save_circuit_breaker(record)
    
    loaded = store.load_circuit_breaker("binance", "BTCUSDT")
    
    assert loaded is not None
    assert loaded.consecutive_blocks == 3
    assert loaded.halt_recommended is True


def test_health_check(store):
    """health() returns status dict."""
    health = store.health()
    
    assert health["status"] == "HEALTHY"
    assert health["schema_version"] == 1
    assert "active_exit_plans" in health
    assert "idempotency_keys" in health


def test_load_registry(store):
    """load_registry returns complete state."""
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
    
    registry = store.load_registry(as_of_ms=2000)
    
    assert registry.version == 1
    assert len(registry.active_positions) == 1
    assert "BTCUSDT" in registry.active_positions
