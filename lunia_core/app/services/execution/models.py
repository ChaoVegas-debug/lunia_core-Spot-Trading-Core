"""
EPOCH C: Execution Bridge Domain Models
Deterministic order plans, execution tracking, queue management, audit events
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    Column, DateTime, Enum, Float, ForeignKey,
    Integer, String, Text, Index
)
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
from sqlalchemy.orm import relationship

from ..auth.database import Base

JSONType = SQLITE_JSON


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ENUMS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ExecutionStatus(str, enum.Enum):
    """ExecutionIntent lifecycle status - EPOCH C"""
    PREVIEW_ONLY = "PREVIEW_ONLY"  # EPOCH B default
    VALIDATED = "VALIDATED"  # Schema validated
    READY = "READY"  # Guards passed, ready for queue
    BLOCKED = "BLOCKED"  # Guard failed
    QUEUED = "QUEUED"  # In execution queue
    SUBMITTING = "SUBMITTING"  # API call in-flight
    SUBMITTED = "SUBMITTED"  # Exchange acknowledged
    PARTIALLY_FILLED = "PARTIALLY_FILLED"  # Partial execution
    FILLED = "FILLED"  # Complete execution
    CANCELLED = "CANCELLED"  # Cancelled
    FAILED = "FAILED"  # Exchange rejection or error
    EXPIRED = "EXPIRED"  # TTL exceeded
    ABORTED = "ABORTED"  # Emergency stop (global_stop flip)


class OrderExecutionStatus(str, enum.Enum):
    """Individual order execution status"""
    PENDING = "PENDING"  # Not yet submitted
    SUBMITTING = "SUBMITTING"  # API call in-flight
    SUBMITTED = "SUBMITTED"  # Exchange acknowledged
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class QueueStatus(str, enum.Enum):
    """Execution queue item status"""
    PENDING = "PENDING"  # Awaiting worker claim
    CLAIMED = "CLAIMED"  # Claimed by worker
    PROCESSING = "PROCESSING"  # Worker processing
    COMPLETED = "COMPLETED"  # Successfully completed
    FAILED = "FAILED"  # Failed after max retries


class ExecutionAuditEventType(str, enum.Enum):
    """EPOCH C audit event types"""
    # Intent lifecycle
    INTENT_READY = "INTENT_READY"
    INTENT_VALIDATED = "INTENT_VALIDATED"
    INTENT_BLOCKED = "INTENT_BLOCKED"
    INTENT_QUEUED = "INTENT_QUEUED"
    
    # Order plan
    ORDERPLAN_CREATED = "ORDERPLAN_CREATED"
    
    # Order execution
    ORDER_SUBMIT_ATTEMPTED = "ORDER_SUBMIT_ATTEMPTED"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_REJECTED = "ORDER_REJECTED"
    ORDER_PARTIAL_FILL = "ORDER_PARTIAL_FILL"
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    
    # Execution failures
    EXECUTION_FAILED = "EXECUTION_FAILED"
    EXECUTION_EXPIRED = "EXECUTION_EXPIRED"
    EXECUTION_ABORTED = "EXECUTION_ABORTED"
    
    # Emergency stops
    GLOBAL_STOP_ABORT = "GLOBAL_STOP_ABORT"
    
    # Compensation (C0.8)
    COMPENSATION_CANCEL_ATTEMPTED = "COMPENSATION_CANCEL_ATTEMPTED"
    COMPENSATION_CANCEL_SUCCESS = "COMPENSATION_CANCEL_SUCCESS"
    COMPENSATION_CANCEL_FAILED = "COMPENSATION_CANCEL_FAILED"
    COMPENSATION_ALREADY_FILLED = "COMPENSATION_ALREADY_FILLED"
    
    # Guards
    CONFLICT_GUARD_BLOCK = "CONFLICT_GUARD_BLOCK"
    SLIPPAGE_GUARD_BLOCK = "SLIPPAGE_GUARD_BLOCK"
    GOVERNANCE_RECHECK_FAIL = "GOVERNANCE_RECHECK_FAIL"
    
    # Recovery
    RECOVERY_RECONCILIATION = "RECOVERY_RECONCILIATION"
    RETRY_EXHAUSTED = "RETRY_EXHAUSTED"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CORE EXECUTION MODELS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class OrderPlan(Base):
    """
    Deterministic decomposition of ExecutionIntent into atomic orders
    
    INVARIANTS:
    - Same intent → same plan (deterministic conversion)
    - plan_hash verifies integrity
    - No in-place mutation (version increment on change)
    """
    __tablename__ = "order_plans"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    execution_intent_id = Column(String(36), ForeignKey("execution_intents.id"), nullable=False, index=True)
    
    # Integrity
    plan_hash = Column(String(64), nullable=False, index=True)
    plan_version = Column(Integer, default=1, nullable=False)
    
    # Order array (JSON)
    orders = Column(JSONType, nullable=False)
    # Structure: [
    #   {
    #     "order_index": 0,
    #     "order_type": "ENTRY" | "TP1" | "TP2" | "SL" | "HEDGE",
    #     "side": "BUY" | "SELL",
    #     "symbol": str,
    #     "quantity": float,
    #     "price": float | null,
    #     "order_style": "MARKET" | "LIMIT" | "STOP_LOSS",
    #     "time_in_force": "GTC" | "IOC" | "FOK",
    #     "client_order_id": str,
    #     "dependencies": [int, ...],
    #     "ttl_seconds": int,
    #     "reduce_only": bool,
    #     "constraints": {"min_qty": float, "max_qty": float, "tick_size": float, "step_size": float}
    #   }
    # ]
    
    # Metadata
    total_estimated_cost = Column(Float, nullable=False)
    estimated_slippage = Column(Float, nullable=False)
    estimated_market_impact = Column(Float, nullable=False)
    
    # Lifecycle
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ttl_seconds = Column(Integer, default=300, nullable=False)
    
    # Relationships
    execution_intent = relationship("ExecutionIntent", back_populates="order_plans")
    order_executions = relationship("OrderExecution", back_populates="order_plan", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("ix_order_plans_intent_id", "execution_intent_id"),
        Index("ix_order_plans_plan_hash", "plan_hash"),
    )


class OrderExecution(Base):
    """
    Individual order execution tracking
    
    INVARIANTS:
    - client_order_id UNIQUE (idempotency)
    - execution_snapshot captured at submission (forensic)
    - No UPDATE on terminal states (append-only history)
    """
    __tablename__ = "order_executions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_plan_id = Column(String(36), ForeignKey("order_plans.id"), nullable=False, index=True)
    order_index = Column(Integer, nullable=False)
    
    # Idempotency (CRITICAL - prevents double execution)
    client_order_id = Column(String(128), nullable=False, unique=True, index=True)
    exchange_order_id = Column(String(128), nullable=True, index=True)
    
    # Order details
    symbol = Column(String(32), nullable=False)
    side = Column(String(8), nullable=False)
    order_type = Column(String(16), nullable=False)
    order_style = Column(String(16), nullable=False)
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=True)
    
    # Status
    status = Column(Enum(OrderExecutionStatus), nullable=False, default=OrderExecutionStatus.PENDING, index=True)
    filled_quantity = Column(Float, default=0.0, nullable=False)
    average_price = Column(Float, nullable=True)
    
    # Execution snapshot (governance + market + portfolio at submission)
    execution_snapshot = Column(JSONType, nullable=True)
    # Structure:
    # {
    #   "governance": {"global_stop": bool, "system_mode": str, ...},
    #   "market_data": {"mid_price": float, "orderbook": {...}, "timestamp": str},
    #   "portfolio": {"equity_usd": float, ...},
    #   "risk_envelope": {"estimated_slippage": float, ...},
    #   "idempotency": {"request_id": str, "job_id": str, "plan_hash": str}
    # }
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    submitted_at = Column(DateTime, nullable=True)
    filled_at = Column(DateTime, nullable=True)
    
    # Exchange response (sanitized - NO SECRETS)
    exchange_response = Column(JSONType, nullable=True)
    
    # Relationships
    order_plan = relationship("OrderPlan", back_populates="order_executions")
    
    __table_args__ = (
        Index("ix_order_executions_plan_id", "order_plan_id"),
        Index("ix_order_executions_status", "status"),
        Index("ix_order_executions_client_order_id", "client_order_id"),
    )


class ExecutionQueue(Base):
    """
    DB-backed execution queue with worker lease management
    
    INVARIANTS:
    - intent_id UNIQUE (prevents double-queue)
    - lease_until enforces worker liveness
    - attempts capped by max_attempts
    """
    __tablename__ = "execution_queue"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    intent_id = Column(String(36), ForeignKey("execution_intents.id"), nullable=False, unique=True, index=True)
    
    # Queue status
    status = Column(Enum(QueueStatus), nullable=False, default=QueueStatus.PENDING, index=True)
    priority = Column(Integer, default=5, nullable=False)
    
    # Worker lease
    lease_until = Column(DateTime, nullable=True)
    worker_id = Column(String(64), nullable=True)
    
    # Retry tracking
    attempts = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=3, nullable=False)
    last_error_code = Column(String(64), nullable=True)
    last_error_message = Column(Text, nullable=True)
    
    # Timestamps
    enqueued_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    claimed_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    execution_intent = relationship("ExecutionIntent")
    
    __table_args__ = (
        Index("ix_execution_queue_status", "status"),
        Index("ix_execution_queue_priority", "priority", "enqueued_at"),
        Index("ix_execution_queue_intent_id", "intent_id"),
    )


class ExecutionAuditEvent(Base):
    """
    Execution audit event - APPEND ONLY
    
    INVARIANTS:
    - No UPDATE or DELETE
    - All state transitions audited (incl. blocked attempts)
    - Correlation IDs enable full trace
    - plan_hash + intent_hash for integrity verification
    """
    __tablename__ = "execution_audit_events"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(Enum(ExecutionAuditEventType), nullable=False, index=True)
    
    # Correlation IDs (forensic traceability)
    intent_id = Column(String(36), ForeignKey("execution_intents.id"), nullable=True, index=True)
    order_plan_id = Column(String(36), nullable=True)
    order_execution_id = Column(String(36), nullable=True)
    request_id = Column(String(64), nullable=True)
    job_id = Column(String(64), nullable=True)
    worker_id = Column(String(64), nullable=True)
    
    # Actor
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    actor_role = Column(String(32), nullable=True)
    
    # Hashes (integrity verification)
    plan_hash = Column(String(64), nullable=True)
    intent_hash = Column(String(64), nullable=True)
    
    # Reason codes (machine-readable)
    reason_codes = Column(JSONType, nullable=True)
    # Structure: ["GLOBAL_STOP_ACTIVE", "PRICE_DRIFT_EXCESSIVE", ...]
    
    # Event metadata
    event_metadata = Column(JSONType, nullable=True)
    # Structure: Flexible, event-specific
    # Examples:
    # - INTENT_BLOCKED: {"guard_type": "PortfolioConflict", "concentration_pct": 35.0}
    # - ORDER_SUBMITTED: {"client_order_id": str, "exchange_order_id": str, "symbol": str}
    # - COMPENSATION_CANCEL_FAILED: {"cancel_result": "TIMEOUT", "exchange_response": {...}}
    
    # Human-readable message
    message = Column(Text, nullable=True)
    
    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    execution_intent = relationship("ExecutionIntent")
    actor = relationship("User")
    
    __table_args__ = (
        Index("ix_execution_audit_intent_ts", "intent_id", "timestamp"),
        Index("ix_execution_audit_event_type_ts", "event_type", "timestamp"),
    )


class WorkerHeartbeat(Base):
    """
    Worker liveness tracking
    
    INVARIANTS:
    - worker_id PRIMARY KEY (one heartbeat per worker)
    - last_heartbeat_at updated every 10s by active workers
    - Stuck workers detected via TTL (>30s = dead)
    """
    __tablename__ = "worker_heartbeats"
    
    worker_id = Column(String(64), primary_key=True)
    last_heartbeat_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    version = Column(String(16), nullable=True)
    hostname = Column(String(128), nullable=True)
