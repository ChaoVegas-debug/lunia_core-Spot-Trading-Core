"""
Phase 7: Execution Journal Models
Signal reasoning persistence - deterministic + synthetic (AI) analysis

INVARIANTS:
- SignalEvent is immutable (no UPDATE allowed)
- AIAnalysis is linked 1:1 with SignalEvent
- All AI inferences are logged (append-only audit trail)
- Timestamps are UTC
- IDs are UUID4
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey,
    Integer, String, Text, Index, Numeric
)
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
from sqlalchemy.orm import relationship

from ..auth.database import Base

JSONType = SQLITE_JSON


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ENUMS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SignalType(str, enum.Enum):
    """Signal action type"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    EXIT = "EXIT"


class AIProvider(str, enum.Enum):
    """LLM provider"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"
    MOCK = "mock"  # For testing


class AIEventType(str, enum.Enum):
    """AI inference event types"""
    AI_INFERENCE = "AI_INFERENCE"
    AI_TIMEOUT = "AI_TIMEOUT"
    AI_VALIDATION_FAILED = "AI_VALIDATION_FAILED"
    AI_CIRCUIT_BREAKER_OPEN = "AI_CIRCUIT_BREAKER_OPEN"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CORE DOMAIN MODELS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SignalEvent(Base):
    """
    Signal Event - Execution Journal Entry
    
    Captures deterministic signal generation from strategy engine.
    Immutable, time-bound, replayable.
    
    INVARIANTS:
    - NO UPDATE allowed (append-only)
    - market_context is snapshot at signal time
    - risk_filters_applied shows which PLN constraints fired
    - deterministic_reasoning explains core logic
    """
    __tablename__ = "signal_events"
    
    # Identity
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Signal Classification
    strategy_id = Column(String(255), nullable=False, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    signal_type = Column(Enum(SignalType), nullable=False)
    confidence = Column(Float)  # 0.0 - 1.0, optional
    
    # Temporal
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Context Snapshots
    market_context = Column(JSONType)
    # Structure:
    # {
    #   "orderbook": {...},
    #   "regime": str,
    #   "volatility": float,
    #   "liquidity": {...}
    # }
    
    risk_filters_applied = Column(JSONType)
    # Structure:
    # {
    #   "pln_passed": bool,
    #   "exposure_cap_hit": bool,
    #   "filters": ["filter_name", ...]
    # }
    
    # Core Intelligence (Deterministic)
    deterministic_reasoning = Column(Text)
    # Human-readable explanation from strategy engine
    # NOT AI-generated, this is the core logic explanation
    
    # Relationships
    ai_analysis = relationship(
        "AIAnalysis",
        back_populates="signal_event",
        uselist=False,  # 1:1 relationship
        cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        Index("ix_signal_strategy_timestamp", "strategy_id", "timestamp"),
        Index("ix_signal_symbol_timestamp", "symbol", "timestamp"),
        Index("ix_signal_type_timestamp", "signal_type", "timestamp"),
    )
    
    def __repr__(self):
        return f"<SignalEvent {self.id[:8]} {self.strategy_id} {self.signal_type} {self.symbol}>"


class AIAnalysis(Base):
    """
    AI Analysis - Synthetic Reasoning Layer
    
    Secondary intelligence: AI interprets deterministic signal.
    This is NOT execution authority - it's explanation and risk flagging.
    
    INVARIANTS:
    - Must pass schema validation (fail-closed)
    - conflicts_with_core = True → UI marks as SECONDARY
    - Provenance always tracked (model, version, hash)
    - Operator feedback collected (hallucination detection)
    """
    __tablename__ = "ai_analysis"
    
    # Identity
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    signal_event_id = Column(
        String(36),
        ForeignKey("signal_events.id"),
        nullable=False,
        unique=True,  # 1:1 with SignalEvent
        index=True
    )
    
    # AI Provenance
    model_revision = Column(String(255), nullable=False)  # e.g. "gpt-4-turbo-2024-04-09"
    reasoning_version = Column(String(50))  # e.g. "core_v6.1"
    ai_constitution_hash = Column(String(64))  # SHA256 of system prompt
    
    # Analysis Output
    summary = Column(Text)  # Concise AI interpretation
    risk_flags = Column(JSONType)  # Array of identified risks
    confirmation = Column(Boolean)  # Does AI agree with core decision?
    confidence_score = Column(Float)  # 0.0 - 1.0
    confidence_reason = Column(Text)
    
    # Conflict Detection
    conflicts_with_core = Column(Boolean, nullable=False, default=False)
    conflict_reason = Column(Text)
    
    # Invalidation Conditions
    invalid_if = Column(JSONType)
    # Structure:
    # [
    #   "data_age > 30s",
    #   "volatility_regime_changed",
    #   "risk_engine_rejected"
    # ]
    
    # Performance Metrics
    latency_ms = Column(Integer)  # AI inference latency
    cost_usd = Column(Numeric(10, 6))  # Inference cost
    
    # Operator Feedback (Human-in-the-Loop)
    operator_feedback = Column(String(20))  # "thumbs_up", "thumbs_down", null
    feedback_comment = Column(Text)  # Optional operator notes
    feedback_timestamp = Column(DateTime)
    
    # Temporal
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    signal_event = relationship("SignalEvent", back_populates="ai_analysis")
    
    __table_args__ = (
        Index("ix_ai_analysis_created", "created_at"),
        Index("ix_ai_analysis_conflicts", "conflicts_with_core"),
    )
    
    def __repr__(self):
        conflict_marker = "⚠" if self.conflicts_with_core else "✓"
        return f"<AIAnalysis {self.id[:8]} {conflict_marker} conf={self.confidence_score}>"


class AIInferenceLog(Base):
    """
    AI Inference Log - Immutable Audit Trail
    
    Every AI API call is logged here.
    Used for: cost tracking, latency monitoring, shadow mode metrics.
    
    INVARIANTS:
    - Append-only (NO UPDATE or DELETE)
    - context_snapshot captures full system state
    - response_valid = True only if schema validation passed
    """
    __tablename__ = "ai_inference_logs"
    
    # Identity
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Event Classification
    event_type = Column(Enum(AIEventType), nullable=False, index=True)
    
    # Context Snapshot (Full System State)
    context_snapshot = Column(JSONType, nullable=False)
    # Structure:
    # {
    #   "system_time": ISO-8601,
    #   "system_state": {...},
    #   "market_state": {...},
    #   "signal": {...},
    #   "pulse_freshness": {...}
    # }
    
    # Token Accounting
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    total_cost_usd = Column(Numeric(10, 6))
    
    # Performance
    latency_ms = Column(Integer)
    
    # Provider Details
    provider = Column(Enum(AIProvider))
    model_name = Column(String(255))
    
    # Validation
    response_valid = Column(Boolean)  # Schema validation result
    validation_error = Column(Text)  # Error message if invalid
    
    # Shadow Mode Flag
    shadow_mode = Column(Boolean, default=True, index=True)
    # If True, AI output was NOT shown to operator
    
    # Temporal
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    __table_args__ = (
        Index("ix_ai_inference_timestamp", "timestamp"),
        Index("ix_ai_inference_shadow", "shadow_mode", "timestamp"),
        Index("ix_ai_inference_provider", "provider", "timestamp"),
    )
    
    def __repr__(self):
        valid_marker = "✓" if self.response_valid else "✗"
        shadow_marker = "🔒" if self.shadow_mode else "👁"
        return f"<AIInferenceLog {self.id[:8]} {valid_marker}{shadow_marker} {self.provider}>"
