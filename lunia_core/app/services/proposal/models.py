"""
EPOCH B: Proposal Domain Models
Versioned, immutable, institutional-grade decision records
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey, 
    Integer, String, Text, Index
)
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
from sqlalchemy.orm import relationship

from ..auth.database import Base

JSONType = SQLITE_JSON


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ENUMS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

import enum

class ProposalStatus(str, enum.Enum):
    """Proposal lifecycle status - matches EPOCH A frontend"""
    DRAFT = "DRAFT"
    PENDING_USER = "PENDING_USER"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    MONITORING = "MONITORING"
    CLOSED = "CLOSED"
    AUTOPSY = "AUTOPSY"
    ARCHIVED = "ARCHIVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    SUPERSEDED = "SUPERSEDED"
    REQUEST_CHANGES = "REQUEST_CHANGES"


class ProposalAction(str, enum.Enum):
    """Trade action type"""
    BUY = "BUY"
    SELL = "SELL"
    HEDGE = "HEDGE"
    REBALANCE = "REBALANCE"


class RiskLabel(str, enum.Enum):
    """Risk classification"""
    LOW_RISK = "LOW_RISK"
    MEDIUM_RISK = "MEDIUM_RISK"
    HIGH_RISK = "HIGH_RISK"
    EXTREME_RISK = "EXTREME_RISK"


class Horizon(str, enum.Enum):
    """Time horizon"""
    INTRADAY = "INTRADAY"
    SWING = "SWING"
    POSITION = "POSITION"
    LONG_TERM = "LONG_TERM"


class DataFreshnessState(str, enum.Enum):
    """Data freshness state - matches EPOCH A"""
    FRESH = "FRESH"
    STALE = "STALE"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"


class ProposalAuditEventType(str, enum.Enum):
    """Audit event types"""
    PROPOSAL_CREATED = "PROPOSAL_CREATED"
    PROPOSAL_VERSIONED = "PROPOSAL_VERSIONED"
    PROPOSAL_SUBMITTED = "PROPOSAL_SUBMITTED"
    PROPOSAL_REVIEWED = "PROPOSAL_REVIEWED"
    PROPOSAL_APPROVED = "PROPOSAL_APPROVED"
    PROPOSAL_REJECTED = "PROPOSAL_REJECTED"
    PROPOSAL_EXPIRED = "PROPOSAL_EXPIRED"
    PROPOSAL_SUPERSEDED = "PROPOSAL_SUPERSEDED"
    PROPOSAL_ARCHIVED = "PROPOSAL_ARCHIVED"
    PROPOSAL_REQUEST_CHANGES = "PROPOSAL_REQUEST_CHANGES"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CORE DOMAIN MODELS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Proposal(Base):
    """
    Proposal Domain Object
    
    INVARIANTS:
    - Immutable per version
    - Any change creates new version
    - governance_snapshot captured at creation (immutable)
    - thesis_dna is structured JSON (chromosomes/genes)
    """
    __tablename__ = "proposals"
    
    # Identity
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    version = Column(Integer, nullable=False, default=1)
    
    # Status
    status = Column(Enum(ProposalStatus), nullable=False, default=ProposalStatus.DRAFT, index=True)
    
    # Classification
    asset = Column(String(32), nullable=False, index=True)
    action = Column(Enum(ProposalAction), nullable=False)
    horizon = Column(Enum(Horizon), nullable=False)
    risk_label = Column(Enum(RiskLabel), nullable=False)
    priority_score = Column(Integer, nullable=False, default=50)  # 0-100
    
    # Governance Snapshot (IMMUTABLE - captured at creation)
    governance_snapshot = Column(JSONType, nullable=False)
    # Structure:
    # {
    #   "global_stop": bool,
    #   "system_mode": str,
    #   "run_mode": str,
    #   "airlock_status": str,
    #   "live_allowed": bool,
    #  "tier": str,
    #   "data_freshness_state": str,
    #   "data_freshness_metrics": {...},
    #   "timestamp": ISO8601
    # }
    
    # Thesis
    thesis_summary = Column(Text, nullable=False)
    thesis_dna = Column(JSONType, nullable=False)
    # Structure (ThesisDNA):
    # {
    #   "chromosomes": {
    #     "technical": [{"key": str, "confidence": float, "weight": float, "evidence_refs": [...], "validation_window": int, "mutation_resistance": float}, ...],
    #     "fundamental": [...],
    #     "sentiment": [...],
    #     "flow": [...],
    #     "macro": [...]
    #   }
    # }
    
    invalidation_rules = Column(JSONType, nullable=True)
    # Structure:
    # {
    #   "machine_readable": [...],
    #   "human_readable": str
    # }
    
    # Evidence
    factor_attribution = Column(JSONType, nullable=False)
    # Structure: [{"factor": str, "weight": int, "confidence": int}, ...]
    # Sum of weights must = 100
    
    model_votes = Column(JSONType, nullable=True)
    # Structure: [{"model_id": str, "vote": str, "confidence": float}, ...]
    
    confidence_score = Column(Float, nullable=False)  # 0.0 - 1.0
    
    devils_advocate = Column(Text, nullable=False)  # MANDATORY counter-case
    
    # Execution Plan Preview (NON-EXECUTABLE)
    execution_plan_preview = Column(JSONType, nullable=True)
    # Structure:
    # {
    #   "entry_zone_low": float,
    #   "entry_zone_high": float,
    #   "take_profit_targets": [float, ...],
    #   "stop_loss": float,
    #   "max_slippage_percent": float
    # }
    
    # Lifecycle
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    supersedes_id = Column(String(36), ForeignKey("proposals.id"), nullable=True)
    
    # Actor tracking
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    rejected_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Timestamps for lifecycle events
    approved_at = Column(DateTime, nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    rejection_reason = Column(String(255), nullable=True)
    
    # Relationships
    supersedes = relationship("Proposal", remote_side=[id], foreign_keys=[supersedes_id])
    execution_intents = relationship("ExecutionIntent", back_populates="proposal")
    audit_events = relationship("ProposalAuditEvent", back_populates="proposal")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    approved_by = relationship("User", foreign_keys=[approved_by_user_id])
    rejected_by = relationship("User", foreign_keys=[rejected_by_user_id])
    
    __table_args__ = (
        Index("ix_proposal_status_asset_created", "status", "asset", "created_at"),
        Index("ix_proposal_version_id", "id", "version"),
    )


class ExecutionIntent(Base):
    """
    Execution Intent - EPOCH B (Preview) + EPOCH C (Execution)
    
    Created on APPROVE (EPOCH B).
    Status = PREVIEW_ONLY until EPOCH C validates and queues.
    EPOCH C: Tracks execution lifecycle through guards → queue → submission → fills.
    """
    __tablename__ = "execution_intents"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    proposal_id = Column(String(36), ForeignKey("proposals.id"), nullable=False, index=True)
    
    # Status (EPOCH B: PREVIEW_ONLY, EPOCH C: full lifecycle - see ExecutionStatus enum)
    status = Column(String(32), nullable=False, default="PREVIEW_ONLY")
    
    # Plan Snapshot (captured at approval)
    plan_snapshot = Column(JSONType, nullable=False)
    # Structure: same as execution_plan_preview from Proposal
    
    # Governance Snapshot at Approval (EPOCH B)
    governance_snapshot_at_approval = Column(JSONType, nullable=False)
    
    # EPOCH C Extensions (added via migration 002)
    execution_params = Column(JSONType, nullable=True)
    # Structure:
    # {
    #   "size_usd": float,
    #   "max_slippage_pct": float,
    #   "ttl_seconds": int,
    #   "execution_strategy": "MARKET" | "LIMIT" | "ICEBERG" | "TWAP"
    # }
    
    market_snapshot_at_approval = Column(JSONType, nullable=True)
    portfolio_snapshot_at_approval = Column(JSONType, nullable=True)
    idempotency_key = Column(String(64), nullable=True, unique=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Relationships
    proposal = relationship("Proposal", back_populates="execution_intents")
    created_by = relationship("User")
    order_plans = relationship("OrderPlan", back_populates="execution_intent", lazy="dynamic")



class ProposalAuditEvent(Base):
    """
    Proposal Audit Event - Append Only
    
    INVARIANTS:
    - No UPDATE or DELETE allowed
    - Must capture full governance context
    - Must capture decision-time confidence & freshness
    """
    __tablename__ = "proposal_audit_events"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    proposal_id = Column(String(36), ForeignKey("proposals.id"), nullable=False, index=True)
    
    # Event classification
    event_type = Column(Enum(ProposalAuditEventType), nullable=False, index=True)
    
    # Actor
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    actor_role = Column(String(32), nullable=True)
    
    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Governance Context (captured at decision time)
    governance_snapshot = Column(JSONType, nullable=False)
    
    # Decision Context
    confidence_score_at_decision = Column(Float, nullable=True)
    data_freshness_state_at_decision = Column(Enum(DataFreshnessState), nullable=True)
    
    # Event metadata
    event_metadata = Column(JSONType, nullable=True)
    # Structure: flexible, depends on event_type
    # Examples:
    # - REJECTED: {"reason": str, "comment": str}
    # - APPROVED: {"size_adjustment": float, "notes": str}
    # - VERSIONED: {"changes": [...]}
    
    # Relationships
    proposal = relationship("Proposal", back_populates="audit_events")
    actor = relationship("User")
    
    __table_args__ = (
        Index("ix_proposal_audit_proposal_ts", "proposal_id", "timestamp"),
        Index("ix_proposal_audit_event_type_ts", "event_type", "timestamp"),
    )
