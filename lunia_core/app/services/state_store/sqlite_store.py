"""
Epoch C.4 — SQLite State Store

Production-grade SQLite backend for lifecycle state persistence.
"""
import sqlite3
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional

from .models import (
    PersistedExitPlanState,
    LifecycleRegistryState,
    IdempotencyRecord,
    CircuitBreakerRecord,
)
from lunia_core.app.services.lifecycle.models import ExitPlan


class SQLiteStateStore:
    """
    SQLite implementation of StateStore protocol.
    
    Features:
    - Strict schema versioning (mismatch → BLOCK)
    - Atomic transactions
    - JSON serialization for nested models
    - Bounded TTL purge
    """
    
    SCHEMA_VERSION = 1
    PURGE_BATCH_SIZE = 1000
    
    def __init__(self, db_path: str):
        """
        Initialize SQLite store.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
    
    def init(self) -> None:
        """Initialize database schema and validate version."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
        # Create schema version table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at_ms INTEGER NOT NULL
            )
        """)
        
        # Check version
        cursor = self.conn.execute("SELECT version FROM schema_version LIMIT 1")
        row = cursor.fetchone()
        
        if row is None:
            # Fresh DB, initialize
            self._create_schema()
            self.conn.execute(
                "INSERT INTO schema_version (version, applied_at_ms) VALUES (?, ?)",
                (self.SCHEMA_VERSION, self._now_ms()),
            )
            self.conn.commit()
        else:
            found_version = row[0]
            if found_version != self.SCHEMA_VERSION:
                raise RuntimeError(
                    f"SCHEMA_MISMATCH_BLOCK: Expected v{self.SCHEMA_VERSION}, "
                    f"found v{found_version}. Manual migration required."
                )
    
    def _create_schema(self) -> None:
        """Create all tables."""
        # Exit plan states
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS exit_plan_states (
                position_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_price REAL NOT NULL,
                quantity REAL NOT NULL,
                exit_plan_json TEXT NOT NULL,
                trailing_peak_price REAL,
                trailing_active INTEGER NOT NULL,
                created_at_ms INTEGER NOT NULL,
                last_updated_ms INTEGER NOT NULL,
                status TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1
            )
        """)
        
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_exit_plan_status ON exit_plan_states(status)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_exit_plan_symbol ON exit_plan_states(symbol)"
        )
        
        # Idempotency keys
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS idempotency_keys (
                key TEXT PRIMARY KEY,
                payload_hash TEXT NOT NULL,
                created_at_ms INTEGER NOT NULL,
                expires_at_ms INTEGER NOT NULL,
                status TEXT NOT NULL,
                committed_at_ms INTEGER
            )
        """)
        
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_idempotency_expires "
            "ON idempotency_keys(expires_at_ms)"
        )
        
        # Circuit breaker states
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS circuit_breaker_states (
                adapter_name TEXT NOT NULL,
                symbol TEXT NOT NULL,
                consecutive_blocks INTEGER NOT NULL,
                last_block_ms INTEGER NOT NULL,
                halt_recommended INTEGER NOT NULL,
                PRIMARY KEY (adapter_name, symbol)
            )
        """)
    
    def health(self) -> Dict[str, Any]:
        """Check storage health."""
        if self.conn is None:
            return {"status": "NOT_INITIALIZED"}
        
        cursor = self.conn.execute("SELECT version FROM schema_version")
        version = cursor.fetchone()[0]
        
        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM exit_plan_states WHERE status = 'ACTIVE'"
        )
        active_plans = cursor.fetchone()[0]
        
        cursor = self.conn.execute("SELECT COUNT(*) FROM idempotency_keys")
        idempotency_count = cursor.fetchone()[0]
        
        return {
            "status": "HEALTHY",
            "schema_version": version,
            "active_exit_plans": active_plans,
            "idempotency_keys": idempotency_count,
            "db_path": self.db_path,
        }
    
    def load_registry(self, as_of_ms: int) -> LifecycleRegistryState:
        """Load complete lifecycle registry."""
        active_plans = self.list_active(as_of_ms)
        
        active_map = {plan.symbol: plan for plan in active_plans}
        
        return LifecycleRegistryState(
            version=1,
            as_of_ms=as_of_ms,
            active_positions=active_map,
            metadata={},
        )
    
    def upsert_exit_plan(self, state: PersistedExitPlanState) -> None:
        """Insert or update exit plan state."""
        exit_plan_json = state.exit_plan.json()
        
        self.conn.execute(
            """
            INSERT OR REPLACE INTO exit_plan_states (
                position_id, symbol, side, entry_price, quantity,
                exit_plan_json, trailing_peak_price, trailing_active,
                created_at_ms, last_updated_ms, status, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                state.position_id,
                state.symbol,
                state.side,
                state.entry_price,
                state.quantity,
                exit_plan_json,
                state.trailing_peak_price,
                1 if state.trailing_active else 0,
                state.created_at_ms,
                state.last_updated_ms,
                state.status,
                state.version,
            ),
        )
        self.conn.commit()
    
    def mark_closed(self, position_id: str, reason: str, closed_at_ms: int) -> None:
        """Mark exit plan as closed."""
        self.conn.execute(
            """
            UPDATE exit_plan_states
            SET status = 'CLOSED', last_updated_ms = ?
            WHERE position_id = ?
            """,
            (closed_at_ms, position_id),
        )
        self.conn.commit()
    
    def list_active(self, as_of_ms: int) -> List[PersistedExitPlanState]:
        """List all active exit plans (including recovered orphans)."""
        cursor = self.conn.execute(
            """
            SELECT * FROM exit_plan_states
            WHERE status IN ('ACTIVE', 'RECOVERED_ORPHAN')
            ORDER BY created_at_ms ASC
            """
        )
        
        results = []
        for row in cursor.fetchall():
            exit_plan = ExitPlan.parse_raw(row["exit_plan_json"])
            
            state = PersistedExitPlanState(
                version=row["version"],
                position_id=row["position_id"],
                symbol=row["symbol"],
                side=row["side"],
                entry_price=row["entry_price"],
                quantity=row["quantity"],
                exit_plan=exit_plan,
                trailing_peak_price=row["trailing_peak_price"],
                trailing_active=bool(row["trailing_active"]),
                created_at_ms=row["created_at_ms"],
                last_updated_ms=row["last_updated_ms"],
                status=row["status"],
            )
            results.append(state)
        
        return results
    
    def reserve_idempotency(
        self, key: str, payload_hash: str, now_ms: int, ttl_ms: int
    ) -> bool:
        """
        Reserve idempotency key.
        
        Returns True if newly reserved, False if already exists.
        """
        expires_at_ms = now_ms + ttl_ms
        
        try:
            self.conn.execute(
                """
                INSERT INTO idempotency_keys (
                    key, payload_hash, created_at_ms, expires_at_ms, status
                ) VALUES (?, ?, ?, ?, 'RESERVED')
                """,
                (key, payload_hash, now_ms, expires_at_ms),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Key already exists
            return False
    
    def commit_idempotency(self, key: str, now_ms: int) -> None:
        """Commit idempotency key after successful execution."""
        self.conn.execute(
            """
            UPDATE idempotency_keys
            SET status = 'COMMITTED', committed_at_ms = ?
            WHERE key = ?
            """,
            (now_ms, key),
        )
        self.conn.commit()
    
    def purge_idempotency(self, now_ms: int) -> int:
        """Purge expired idempotency keys (bounded delete)."""
        cursor = self.conn.execute(
            """
            DELETE FROM idempotency_keys
            WHERE expires_at_ms < ?
            LIMIT ?
            """,
            (now_ms, self.PURGE_BATCH_SIZE),
        )
        self.conn.commit()
        return cursor.rowcount
    
    def load_circuit_breaker(
        self, adapter_name: str, symbol: str
    ) -> Optional[CircuitBreakerRecord]:
        """Load circuit breaker state."""
        cursor = self.conn.execute(
            """
            SELECT * FROM circuit_breaker_states
            WHERE adapter_name = ? AND symbol = ?
            """,
            (adapter_name, symbol),
        )
        
        row = cursor.fetchone()
        if row is None:
            return None
        
        return CircuitBreakerRecord(
            adapter_name=row["adapter_name"],
            symbol=row["symbol"],
            consecutive_blocks=row["consecutive_blocks"],
            last_block_ms=row["last_block_ms"],
            halt_recommended=bool(row["halt_recommended"]),
        )
    
    def save_circuit_breaker(self, record: CircuitBreakerRecord) -> None:
        """Save circuit breaker state."""
        self.conn.execute(
            """
            INSERT OR REPLACE INTO circuit_breaker_states (
                adapter_name, symbol, consecutive_blocks,
                last_block_ms, halt_recommended
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                record.adapter_name,
                record.symbol,
                record.consecutive_blocks,
                record.last_block_ms,
                1 if record.halt_recommended else 0,
            ),
        )
        self.conn.commit()
    
    def _now_ms(self) -> int:
        """Get current timestamp in milliseconds."""
        import time
        return int(time.time() * 1000)
