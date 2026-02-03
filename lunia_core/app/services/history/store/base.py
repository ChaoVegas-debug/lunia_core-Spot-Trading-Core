"""
EPOCH D Phase D2: Storage Interface Base
Canonical storage contract for historical data
"""
from __future__ import annotations

from typing import List, Optional, Protocol
from pydantic import BaseModel, Field
from enum import Enum

from ..models import HistoricalTick


class ErrorCode(str, Enum):
    """Error codes for D2 operations"""
    HIST_SNAPSHOT_INVALID = "HIST_SNAPSHOT_INVALID"
    HIST_SEGMENT_MISSING = "HIST_SEGMENT_MISSING"
    HIST_SEGMENT_CORRUPT = "HIST_SEGMENT_CORRUPT"
    HIST_MANIFEST_MISSING = "HIST_MANIFEST_MISSING"
    HIST_MANIFEST_CORRUPT = "HIST_MANIFEST_CORRUPT"
    HIST_SCHEMA_TOO_NEW = "HIST_SCHEMA_TOO_NEW"
    HIST_SCHEMA_UNSUPPORTED = "HIST_SCHEMA_UNSUPPORTED"
    HIST_GAP_DETECTED = "HIST_GAP_DETECTED"
    HIST_INSUFFICIENT_SAMPLES = "HIST_INSUFFICIENT_SAMPLES"
    HIST_CHECKSUM_MISMATCH = "HIST_CHECKSUM_MISMATCH"
    HIST_PATH_UNSAFE = "HIST_PATH_UNSAFE"
    HIST_WRITE_FAILED = "HIST_WRITE_FAILED"
    HIST_UNKNOWN_ERROR = "HIST_UNKNOWN_ERROR"


class AppendResult(BaseModel):
    """Result from append operation"""
    ok: bool
    error_code: Optional[ErrorCode] = None
    metadata: dict = Field(default_factory=dict)


class ReadResult(BaseModel):
    """Result from read operation"""
    ok: bool
    ticks: Optional[List[HistoricalTick]] = None
    error_code: Optional[ErrorCode] = None
    metadata: dict = Field(default_factory=dict)


class HealthResult(BaseModel):
    """Health check result"""
    ok: bool
    error_code: Optional[ErrorCode] = None
    checks: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)


class IHistoricalStore(Protocol):
    """
    Historical storage interface
    
    LOC KED INVARIANTS:
    - Append-only (no updates/deletes)
    - Idempotent (re-append same tick → no duplicate)
    - Deterministic ordering (timestamp asc, version asc)
    - Fail-closed reads (no partial windows)
    - Persistent (except InMemory test-only)
    """
    
    def append_tick(self, tick: HistoricalTick) -> AppendResult:
        """
        Append tick with idempotency
        
        Args:
            tick: HistoricalTick to append
        
        Returns:
            AppendResult (ok=True if successful)
        """
        ...
    
    def get_ticks(
        self,
        symbol: str,
        start_ms: int,
        end_ms: int
    ) -> ReadResult:
        """
        Read ticks in time range (fail-closed)
        
        Args:
            symbol: Symbol to read
            start_ms: Start timestamp (inclusive)
            end_ms: End timestamp (inclusive)
        
        Returns:
            ReadResult with ticks or error
        """
        ...
    
    def count(self, symbol: str) -> int:
        """Count total ticks for symbol"""
        ...
    
    def health(self) -> HealthResult:
        """
        Health check
        
        Checks:
        - Disk accessibility
        - Manifest readability
        - Schema compatibility
        - Optional checksum sampling
        """
        ...
