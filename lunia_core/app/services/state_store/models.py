"""
Epoch C.4 — State Store Models

Frozen Pydantic models for persisted lifecycle state.
"""
from typing import Dict, Any, Optional, Literal
from pydantic import BaseModel, Field

from lunia_core.app.services.lifecycle.models import ExitPlan


class PersistedExitPlanState(BaseModel):
    """
    Persisted exit plan state with lifecycle metadata.
    
    Immutable snapshot of position's exit plan and trailing stop state.
    """
    version: int = Field(default=1, description="Schema version")
    position_id: str = Field(..., description="Unique position identifier")
    symbol: str = Field(..., description="Trading symbol")
    side: Literal["LONG", "SHORT"] = Field(..., description="Position side")
    entry_price: float = Field(..., gt=0, description="Position entry price")
    quantity: float = Field(..., gt=0, description="Position quantity")
    exit_plan: ExitPlan = Field(..., description="Exit plan configuration")
    
    # Trailing stop state
    trailing_peak_price: Optional[float] = Field(
        default=None, description="Peak price for trailing stop (if active)"
    )
    trailing_active: bool = Field(
        default=False, description="Whether trailing stop is currently active"
    )
    
    # Lifecycle metadata
    created_at_ms: int = Field(..., gt=0, description="Plan creation timestamp")
    last_updated_ms: int = Field(..., gt=0, description="Last update timestamp")
    status: Literal[
        "ACTIVE",
        "CLOSED",
        "ORPHANED",
        "CLOSED_EXTERNALLY",
        "RECOVERED_ORPHAN",
    ] = Field(default="ACTIVE", description="Lifecycle status")
    
    class Config:
        frozen = True
        use_enum_values = True


class LifecycleRegistryState(BaseModel):
    """
    Complete registry of active lifecycle state.
    
    Represents the entire state of the lifecycle manager at a point in time.
    """
    version: int = Field(default=1, description="Schema version")
    as_of_ms: int = Field(..., gt=0, description="Snapshot timestamp")
    active_positions: Dict[str, PersistedExitPlanState] = Field(
        default_factory=dict, description="Map of symbol → persisted state"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional registry metadata"
    )
    
    class Config:
        frozen = True


class IdempotencyRecord(BaseModel):
    """
    Idempotency key record with TTL.
    
    Prevents duplicate exit intents from being executed multiple times.
    """
    key: str = Field(..., description="Idempotency key")
    payload_hash: str = Field(..., description="SHA256 hash of intent payload")
    created_at_ms: int = Field(..., gt=0, description="Key creation timestamp")
    ttl_ms: int = Field(..., gt=0, description="Time-to-live in milliseconds")
    status: Literal["RESERVED", "COMMITTED", "EXPIRED"] = Field(
        default="RESERVED", description="Key lifecycle status"
    )
    
    @property
    def expires_at_ms(self) -> int:
        """Calculate expiration timestamp."""
        return self.created_at_ms + self.ttl_ms
    
    def is_expired(self, now_ms: int) -> bool:
        """Check if key is expired."""
        return now_ms >= self.expires_at_ms
    
    class Config:
        frozen = True


class CircuitBreakerRecord(BaseModel):
    """
    Circuit breaker state for exchange adapters.
    
    Tracks consecutive blocks and halt recommendations.
    """
    adapter_name: str = Field(..., description="Exchange adapter name")
    symbol: str = Field(..., description="Trading symbol")
    consecutive_blocks: int = Field(default=0, ge=0, description="Consecutive block count")
    last_block_ms: int = Field(..., gt=0, description="Last block timestamp")
    halt_recommended: bool = Field(
        default=False, description="Whether trading halt is recommended"
    )
    
    class Config:
        frozen = True
        use_enum_values = True
