"""
EPOCH D Phase D2: Historical Memory Models
Canonical tick data model with schema versioning
"""
from __future__ import annotations

import time
from typing import Optional
from pydantic import BaseModel, Field, validator


# Schema version for evolution tracking
CURRENT_SCHEMA_VERSION = 1


class HistoricalTick(BaseModel):
    """
    Historical tick/quote snapshot
    
    CRITICAL: This is tick/quote data from MarketSnapshot
    DO NOT synthesize OHLCV from ticks
    
    Schema versioning:
    - schema_version field tracks evolution
    - Reads must handle schema compatibility
    - Too-new schema → fail-closed
    """
    
    # Primary data
    symbol: str = Field(..., description="Trading pair")
    timestamp_ms: int = Field(..., description="Event timestamp (from snapshot)")
    
    # Price data (from MarketSnapshot)
    mid_price: float = Field(..., description="Mid price")
    bid: Optional[float] = Field(None, description="Best bid")
    ask: Optional[float] = Field(None, description="Best ask")
    
    # Provenance & dedup
    snapshot_version: int = Field(..., description="Snapshot version (for dedup key)")
    source_snapshot_id: Optional[str] = Field(None, description="Optional snapshot ID")
    
    # Metadata
    ingested_at_ms: int = Field(default_factory=lambda: int(time.time() * 1000), description="Ingestion timestamp")
    schema_version: int = Field(default=CURRENT_SCHEMA_VERSION, description="Schema version")
    
    @property
    def dedup_key(self) -> tuple:
        """
        Idempotency key
        
        Stable, collision-resistant key for deduplication
        Format: (symbol, timestamp_ms, snapshot_version)
        """
        return (self.symbol, self.timestamp_ms, self.snapshot_version)
    
    @validator('symbol')
    def validate_symbol(cls, v):
        """Sanitize symbol (security: prevent path traversal)"""
        # Allow only safe characters
        import re
        if not re.match(r'^[A-Z0-9_:\-/]+$', v):
            raise ValueError(f"Invalid symbol characters: {v}")
        if '..' in v or '/' in v[1:]:  # Prevent path traversal
            raise ValueError(f"Symbol contains unsafe path components: {v}")
        return v
    
    @validator('timestamp_ms', 'ingested_at_ms')
    def validate_timestamps(cls, v):
        """Validate timestamps are reasonable"""
        if v < 0 or v > int(time.time() * 1000) + 86400000:  # Future + 1 day
            raise ValueError(f"Invalid timestamp: {v}")
        return v
    
    @validator('mid_price', 'bid', 'ask')
    def validate_prices(cls, v):
        """Validate prices are positive if present"""
        if v is not None and v <= 0:
            raise ValueError(f"Price must be positive: {v}")
        return v
    
    class Config:
        frozen = True  # Immutable
