"""Break-Glass Emergency Access (PHASE 7 - HASHED-ONLY, ONE-TIME, REVOCABLE)

High-entropy tokens with SHA256 storage, TTL enforcement, and full audit trail.
"""
import os
import json
import hashlib
import secrets
import threading
import fcntl
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from contextlib import contextmanager


class BreakGlassManager:
    """Manages break-glass emergency tokens with hashed-only storage."""
    
    def __init__(self, storage_path: str = "data/break_glass.json"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.storage_path.parent / "break_glass.lock"
        self._lock = threading.RLock()
    
    @contextmanager
    def _file_lock(self):
        """Cross-process file lock."""
        with open(self.lock_path, 'w') as lock_fd:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
    
    def _load_storage(self) -> Dict[str, Any]:
        """Load storage or return empty dict."""
        if not self.storage_path.exists():
            return {}
        
        with open(self.storage_path, 'r') as f:
            return json.load(f)
    
    def _save_storage(self, data: Dict[str, Any]):
        """Atomic write with fsync."""
        fd, temp_path = tempfile.mkstemp(
            dir=str(self.storage_path.parent),
            prefix=f".{self.storage_path.name}.",
            suffix=".tmp"
        )
        
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(data, f, indent=2, sort_keys=True)
                f.flush()
                os.fsync(f.fileno())
            
            os.rename(temp_path, self.storage_path)
            
            try:
                dir_fd = os.open(self.storage_path.parent, os.O_RDONLY)
                os.fsync(dir_fd)
                os.close(dir_fd)
            except (OSError, AttributeError):
                pass
        except Exception as e:
            try:
                os.unlink(temp_path)
            except:
                pass
            raise RuntimeError(f"[BREAK_GLASS_STORAGE_ERROR] {e}")
    
    def issue(
        self,
        incident_id: str,
        issued_by: str,
        reason: str,
        ttl_seconds: int = 900
    ) -> tuple[str, Dict[str, Any]]:
        """Issue break-glass token.
        
        Args:
            incident_id: Unique incident identifier
            issued_by: Actor issuing the token
            reason: Redacted reason (will be stored)
            ttl_seconds: Time to live (default 900s, max 3600s)
        
        Returns:
            (plaintext_token, metadata) - plaintext NEVER stored
        """
        if ttl_seconds > 3600:
            raise ValueError("TTL must be <= 3600 seconds")
        if ttl_seconds < 1:
            raise ValueError("TTL must be >= 1 second")
        
        with self._lock, self._file_lock():
            storage = self._load_storage()
            
            # Check if incident_id already exists
            if incident_id in storage:
                raise ValueError(f"Incident ID {incident_id} already exists")
            
            # Generate high-entropy token (256 bits)
            plaintext_token = secrets.token_urlsafe(32)  # 32 bytes = 256 bits
            
            # Hash token for storage
            token_hash = hashlib.sha256(plaintext_token.encode('utf-8')).hexdigest()
            
            # Create metadata
            now = datetime.utcnow()
            expires_at = now + timedelta(seconds=ttl_seconds)
            
            metadata = {
                "incident_id": incident_id,
                "token_hash": token_hash,
                "issued_at": now.isoformat() + "Z",
                "expires_at": expires_at.isoformat() + "Z",
                "issued_by": issued_by,
                "reason": reason[:500],  # Truncate
                "ttl_seconds": ttl_seconds,
                "used_at": None,
                "revoked_at": None
            }
            
            # Store by incident_id
            storage[incident_id] = metadata
            self._save_storage(storage)
            
            return (plaintext_token, metadata)
    
    def validate(self, plaintext_token: str) -> tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Validate break-glass token.
        
        Returns:
            (is_valid, error_code, metadata)
            
        Error codes:
            - BREAK_GLASS_NOT_FOUND
            - BREAK_GLASS_USED
            - BREAK_GLASS_EXPIRED
            - BREAK_GLASS_REVOKED
        """
        with self._lock, self._file_lock():
            storage = self._load_storage()
            
            # Compute hash
            token_hash = hashlib.sha256(plaintext_token.encode('utf-8')).hexdigest()
            
            # Find by token_hash
            metadata = None
            for incident_id, meta in storage.items():
                if meta["token_hash"] == token_hash:
                    metadata = meta
                    break
            
            if not metadata:
                return (False, "BREAK_GLASS_NOT_FOUND", None)
            
            # Check if already used
            if metadata["used_at"] is not None:
                return (False, "BREAK_GLASS_USED", metadata)
            
            # Check if revoked
            if metadata["revoked_at"] is not None:
                return (False, "BREAK_GLASS_REVOKED", metadata)
            
            # Check if expired
            now = datetime.utcnow()
            expires_at = datetime.fromisoformat(metadata["expires_at"].replace("Z", ""))
            if now > expires_at:
                return (False, "BREAK_GLASS_EXPIRED", metadata)
            
            return (True, None, metadata)
    
    def mark_used(self, plaintext_token: str) -> Dict[str, Any]:
        """Mark token as used (one-time burn).
        
        Returns:
            Updated metadata
            
        Raises:
            ValueError if token invalid or already used
        """
        with self._lock, self._file_lock():
            is_valid, error_code, metadata = self.validate(plaintext_token)
            
            if not is_valid:
                raise ValueError(f"Token invalid: {error_code}")
            
            # Mark used atomically
            storage = self._load_storage()
            incident_id = metadata["incident_id"]
            storage[incident_id]["used_at"] = datetime.utcnow().isoformat() + "Z"
            
            self._save_storage(storage)
            
            return storage[incident_id]
    
    def revoke(self, incident_id: Optional[str] = None, token_hash: Optional[str] = None) -> Dict[str, Any]:
        """Revoke break-glass token by incident_id or token_hash.
        
        Returns:
            Updated metadata
            
        Raises:
            ValueError if not found
        """
        if not incident_id and not token_hash:
            raise ValueError("Must provide incident_id or token_hash")
        
        with self._lock, self._file_lock():
            storage = self._load_storage()
            
            # Find target
            target_incident_id = None
            
            if incident_id:
                if incident_id not in storage:
                    raise ValueError(f"Incident ID {incident_id} not found")
                target_incident_id = incident_id
            elif token_hash:
                for iid, meta in storage.items():
                    if meta["token_hash"] == token_hash:
                        target_incident_id = iid
                        break
                
                if not target_incident_id:
                    raise ValueError(f"Token hash not found")
            
            # Mark revoked
            storage[target_incident_id]["revoked_at"] = datetime.utcnow().isoformat() + "Z"
            self._save_storage(storage)
            
            return storage[target_incident_id]
    
    def get_by_incident_id(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata by incident_id."""
        with self._lock, self._file_lock():
            storage = self._load_storage()
            return storage.get(incident_id)
