"""Persistent Governance Store (PHASE 5.1 - HARDENED, NO DEADLOCKS, NO RACES)

Transaction-based governance with locked_transaction context manager.
"""
import os
import json
import hashlib
import threading
import fcntl
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from contextlib import contextmanager


class RiskConfigStore:
    """Persistent governance - transaction-safe, deadlock-free."""
    
    def __init__(self, config_path: str = "data/risk_config.json"):
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.config_path.parent / "risk_config.lock"
        self._thread_lock = threading.RLock()  # REENTRANT lock (F1 fix)
        self._current_state: Optional[Dict[str, Any]] = None
        
    @contextmanager
    def locked_transaction(self):
        """Transaction context: holds thread lock + cross-process file lock."""
        with self._thread_lock:
            with self._file_lock():
                yield
    
    def load_or_initialize(self) -> Dict[str, Any]:
        """Load config or create default."""
        with self.locked_transaction():
            return self._load_or_initialize_nolock()
    
    def get_current_state(self) -> Dict[str, Any]:
        """Get current state (hot reload - always reloads from disk)."""
        with self.locked_transaction():
            return self._load_or_initialize_nolock()
    
    def update_mode(self, new_mode: str, actor: str, reason: str, request_id: str) -> Dict[str, Any]:
        """Update mode (caller must hold locked_transaction)."""
        # Assumes caller holds locked_transaction
        current = self._load_or_initialize_nolock()
        
        new_state = {
            **current,
            "version": current["version"] + 1,
            "mode": new_mode,
            "updated_at": datetime.utcnow().isoformat() + "Z",
            "last_actor": actor,
            "last_reason": reason[:500],
            "last_request_id": request_id
        }
        
        new_state["checksum"] = self._compute_checksum(new_state)
        self._atomic_write_nolock(new_state)
        self._current_state = new_state
        
        return new_state
    
    def update_halt(self, halt: bool, actor: str, reason: str, request_id: str) -> Dict[str, Any]:
        """Update halt (caller must hold locked_transaction)."""
        # Assumes caller holds locked_transaction
        current = self._load_or_initialize_nolock()
        
        new_state = {
            **current,
            "version": current["version"] + 1,
            "is_halted": halt,
            "updated_at": datetime.utcnow().isoformat() + "Z",
            "last_actor": actor,
            "last_reason": reason[:500],
            "last_request_id": request_id
        }
        
        new_state["checksum"] = self._compute_checksum(new_state)
        self._atomic_write_nolock(new_state)
        self._current_state = new_state
        
        return new_state
    
    def snapshot_backup(self) -> Optional[Dict[str, Any]]:
        """Public backup (with locks)."""
        with self.locked_transaction():
            return self.snapshot_backup_nolock()
    
    def rollback(self, backup_state: Dict[str, Any]):
        """Public rollback (with locks)."""
        with self.locked_transaction():
            self.rollback_nolock(backup_state)
    
    def snapshot_backup_nolock(self) -> Optional[Dict[str, Any]]:
        """Backup (assumes caller holds locks)."""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return None
    
    def rollback_nolock(self, backup_state: Dict[str, Any]):
        """Rollback (assumes caller holds locks)."""
        self._atomic_write_nolock(backup_state)
        self._current_state = backup_state
    
    def _load_or_initialize_nolock(self) -> Dict[str, Any]:
        """Load without acquiring locks (internal helper)."""
        if not self.config_path.exists():
            default_state = {
                "version": 1,
                "mode": "SHADOW",
                "is_halted": False,
                "max_drawdown": "0.25",
                "created_at": datetime.utcnow().isoformat() + "Z",
                "updated_at": datetime.utcnow().isoformat() + "Z"
            }
            default_state["checksum"] = self._compute_checksum(default_state)
            self._atomic_write_nolock(default_state)
            self._current_state = default_state
            return default_state
        
        with open(self.config_path, 'r') as f:
            state = json.load(f)
        
        stored_checksum = state.get("checksum")
        computed_checksum = self._compute_checksum(state)
        
        if stored_checksum != computed_checksum:
            raise RuntimeError("[INTEGRITY_CHECK_FAILED] Config checksum mismatch")
        
        self._current_state = state
        return state
    
    def _compute_checksum(self, state: Dict[str, Any]) -> str:
        """Compute SHA256 checksum."""
        canonical = {k: v for k, v in state.items() if k != "checksum"}
        canonical_json = json.dumps(canonical, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()
    
    def _atomic_write_nolock(self, state: Dict[str, Any]):
        """Atomic write with fsync (assumes caller holds locks)."""
        fd, temp_path = tempfile.mkstemp(
            dir=str(self.config_path.parent),
            prefix=f".{self.config_path.name}.",
            suffix=".tmp"
        )
        
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(state, f, indent=2, sort_keys=True)
                f.flush()
                os.fsync(f.fileno())
            
            os.rename(temp_path, self.config_path)
            
            try:
                dir_fd = os.open(self.config_path.parent, os.O_RDONLY)
                os.fsync(dir_fd)
                os.close(dir_fd)
            except (OSError, AttributeError):
                pass
                
        except Exception as e:
            try:
                os.unlink(temp_path)
            except:
                pass
            raise RuntimeError(f"[GOVERNANCE_PERSISTENCE_ERROR] Write failed: {e}")
    
    def _file_lock(self):
        """Cross-process file lock context manager."""
        return _FileLock(self.lock_path)


class _FileLock:
    """Cross-process file lock using fcntl."""
    
    def __init__(self, lock_path: Path):
        self.lock_path = lock_path
        self.lock_fd = None
    
    def __enter__(self):
        self.lock_fd = open(self.lock_path, 'w')
        fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_EX)
        return self
    
    def __exit__(self, *args):
        if self.lock_fd:
            fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_UN)
            self.lock_fd.close()
