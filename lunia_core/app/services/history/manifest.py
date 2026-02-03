"""
EPOCH D Phase D2: Manifest & Shared Utilities
Manifest-as-source-of-truth with checksums, atomic writes, partition locks
"""
import os
import json
import hashlib
import threading
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
from pathlib import Path


# Manifest versioning
CURRENT_MANIFEST_VERSION = 1


class SegmentInfo(BaseModel):
    """Segment metadata in manifest"""
    segment_path: str
    min_ts_ms: int
    max_ts_ms: int
    row_count: int
    schema_version: int
    checksum_alg: str = "sha256"
    checksum: str
    created_at_ms: int


class Manifest(BaseModel):
    """Partition manifest (source of truth)"""
    manifest_version: int = CURRENT_MANIFEST_VERSION
    symbol: str
    schema_version: int
    segments: List[SegmentInfo] = Field(default_factory=list)
    
    def to_dict(self):
        return self.dict()
    
    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)


class ManifestManager:
    """Thread-safe manifest operations with atomic writes"""
    
    def __init__(self, root_path: str):
        self.root_path = Path(root_path)
        self._locks: Dict[str, threading.Lock] = {}
        self._locks_lock = threading.Lock()
    
    def _get_partition_lock(self, symbol: str) -> threading.Lock:
        """Get lock for symbol partition (single writer per partition)"""
        with self._locks_lock:
            if symbol not in self._locks:
                self._locks[symbol] = threading.Lock()
            return self._locks[symbol]
    
    def _manifest_path(self, symbol: str) -> Path:
        """Get manifest path for symbol"""
        return self.root_path / symbol / "manifest.json"
    
    def load_manifest(self, symbol: str) -> Optional[Manifest]:
        """Load manifest (fail-closed on corrupt/missing)"""
        manifest_path = self._manifest_path(symbol)
        
        if not manifest_path.exists():
            return None
        
        try:
            with open(manifest_path, 'r') as f:
                data = json.load(f)
            return Manifest.from_dict(data)
        except Exception:
            return None  # Corrupt manifest
    
    def save_manifest(self, manifest: Manifest) -> bool:
        """
        Save manifest atomically
        
        Uses temp + os.replace for crash safety
        """
        manifest_path = self._manifest_path(manifest.symbol)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        
        temp_path = manifest_path.with_suffix('.tmp')
        
        try:
            # Write to temp
            with open(temp_path, 'w') as f:
                json.dump(manifest.to_dict(), f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            
            # Atomic replace
            os.replace(temp_path, manifest_path)
            
            # Fsync directory (best effort)
            try:
                dir_fd = os.open(manifest_path.parent, os.O_RDONLY)
                os.fsync(dir_fd)
                os.close(dir_fd)
            except: pass
            
            return True
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            return False


def compute_checksum(file_path: Path, algorithm: str = "sha256") -> str:
    """Compute file checksum"""
    h = hashlib.sha256() if algorithm == "sha256" else hashlib.md5()
    
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    
    return h.hexdigest()


def verify_checksum(file_path: Path, expected: str, algorithm: str = "sha256") -> bool:
    """Verify file checksum"""
    actual = compute_checksum(file_path, algorithm)
    return actual == expected


def sanitize_symbol(symbol: str) -> Tuple[bool, str]:
    """
    Sanitize symbol (prevent path traversal)
    
    Returns: (is_safe, sanitized_symbol)
    """
    import re
    
    # Check for safe characters
    if not re.match(r'^[A-Z0-9_:\-]+$', symbol):
        return (False, symbol)
    
    # Prevent path traversal
    if '..' in symbol or symbol.startswith('/'):
        return (False, symbol)
    
    return (True, symbol)
