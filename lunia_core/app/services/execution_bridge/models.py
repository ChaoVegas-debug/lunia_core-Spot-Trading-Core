"""
Epoch C: Execution Bridge — Models

Immutable models for Order lifecycle: Intent → Plan → Result.
"""
import enum
from typing import Optional, Dict
from datetime import datetime
from pydantic import BaseModel, Field


class OrderSide(str, enum.Enum):
    """Order side"""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, enum.Enum):
    """Order type"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class TimeInForce(str, enum.Enum):
    """Time in force"""
    IOC = "IOC"  # Immediate or Cancel (default)
    GTC = "GTC"  # Good til Cancel
    FOK = "FOK"  # Fill or Kill


class OrderStatus(str, enum.Enum):
    """Order plan status"""
    PLANNED = "PLANNED"      # Plan created, not executed
    EXECUTED = "EXECUTED"    # Successfully executed
    ABORTED = "ABORTED"      # Aborted (e.g., Council veto)
    FAILED = "FAILED"        # Execution failed


class OrderIntent(BaseModel):
    """
    Intent to execute (derived from CouncilVerdict).
    
    This is the first transformation from Council approval.
    """
    id: str = Field(default_factory=lambda: str(__import__('uuid').uuid4()))
    verdict_id: str = Field(..., description="Council verdict ID (idempotency key)")
    symbol: str
    side: OrderSide
    intent_confidence: float = Field(..., ge=0.0, le=1.0)
    constraints: Dict = Field(default_factory=dict, description="Risk constraints from Council")
    
    class Config:
        frozen = True
        use_enum_values = True


class OrderPlan(BaseModel):
    """
    Deterministic order plan with sizing.
    
    This is the executable specification (the "hand").
    """
    id: str = Field(default_factory=lambda: str(__import__('uuid').uuid4()))
    verdict_id: str = Field(..., description="Unique idempotency key")
    symbol: str
    side: OrderSide
    
    # Quantity (Calculated Deterministically)
    quantity: float = Field(..., gt=0, description="Order quantity in base asset")
    
    # Order Parameters
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = Field(None, description="Limit price (for LIMIT orders)")
    time_in_force: TimeInForce = TimeInForce.IOC
    
    # Audit Trail
    sizing_logic: str = Field(..., description="Human-readable sizing calculation proof")
    status: OrderStatus = OrderStatus.PLANNED
    
    created_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + 'Z'
    )
    
    class Config:
        frozen = True
        use_enum_values = True


class ExecutionResult(BaseModel):
    """
    Immutable result of order execution.
    
    This records what actually happened (success or failure).
    """
    id: str = Field(default_factory=lambda: str(__import__('uuid').uuid4()))
    plan_id: str = Field(..., description="OrderPlan ID")
    verdict_id: str = Field(..., description="Council verdict ID")
    
    # Execution Status
    executed: bool = Field(..., description="True if order placed successfully")
    
    # Exchange Response
    exchange_order_id: Optional[str] = Field(None, description="Exchange order ID (if executed)")
    filled_qty: float = Field(0.0, description="Filled quantity")
    avg_price: Optional[float] = Field(None, description="Average fill price")
    
    # Error Info
    error_code: Optional[str] = Field(None)
    error_detail: Optional[str] = Field(None)
    
    # Temporal
    executed_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + 'Z'
    )
    
    class Config:
        frozen = True


class ExecutionBridgeEvent(BaseModel):
    """
    Journal event for execution traceability.
    
    Queryable schema for full execution audit trail.
    
    EVENT TYPES (Epoch C + C.1):
    - RECEIVED: Verdict received
    - PLANNED: Order plan created
    - SUBMITTED: Order submitted to exchange (NEW in C.1)
    - RETRY_ATTEMPT: Retry attempt logged (NEW in C.1)
    - PARTIALLY_FILLED: Partial fill detected (NEW in C.1)
    - FILLED: Fully filled (NEW in C.1)
    - EXECUTED: Execution completed (legacy)
    - CANCELLED: Order cancelled (NEW in C.1)
    - REJECTED_BY_EXCHANGE: Exchange rejected order (NEW in C.1)
    - RATE_LIMIT_BLOCKED: Rate limit prevented submission (NEW in C.1)
    - ABORTED: Execution aborted
    - ERROR: Execution error
    """
    id: str = Field(default_factory=lambda: str(__import__('uuid').uuid4()))
    verdict_id: str = Field(..., description="Council verdict ID (join key)")
    event_type: str = Field(..., description="Event type (see docstring)")
    
    # Context
    symbol: str
    side: Optional[str] = None
    quantity: Optional[float] = None
    
    # Details
    detail: str = Field("", description="Human-readable event detail")
    metadata: Dict = Field(default_factory=dict)
    
    # Epoch C.1: Exchange Adapter Extensions (ADDITIVE)
    adapter_name: Optional[str] = Field(
        None,
        description="Exchange adapter name (e.g., 'binance_sandbox')"
    )
    exchange_order_id: Optional[str] = Field(
        None,
        description="Exchange's native order ID"
    )
    raw_exchange_payload: Optional[Dict] = Field(
        None,
        description="Full exchange response (for forensics)"
    )
    retry_attempt: Optional[int] = Field(
        None,
        description="Retry attempt number (0-indexed)"
    )
    
    # Temporal
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + 'Z'
    )

