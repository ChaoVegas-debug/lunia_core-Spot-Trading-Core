"""
AI Budget Usage Model - Persistent Daily Spend Tracking

CRITICAL: Budget state MUST survive backend restarts.
This model stores daily AI spend in the database for persistence.
"""

from sqlalchemy import Column, String, Integer, Numeric, Date, DateTime, Index
from sqlalchemy.sql import func
from datetime import datetime
import uuid

from ..auth.database import Base


class AIBudgetUsage(Base):
    """
    Daily AI budget usage tracking (persistent).
    
    This table stores aggregated AI spend per day/provider/model.
    
    CRITICAL INVARIANTS:
    - One row per (date, provider, model) combination
    - Updates are atomic (use ON CONFLICT UPDATE)
    - No DELETE allowed (append-only for audit)
    
    PERSISTENCE GUARANTEE:
    Backend restart MUST NOT reset budget counters.
    This table is the source of truth for daily spend.
    """
    
    __tablename__ = "ai_budget_usage"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Partition key: UTC calendar day
    date = Column(Date, nullable=False, index=True)
    """UTC calendar day (YYYY-MM-DD). Budget resets daily."""
    
    # AI provider and model
    provider = Column(String(50), nullable=False)
    """Provider name (e.g. 'openai', 'anthropic', 'mock')"""
    
    model = Column(String(100))
    """Model name (e.g. 'gpt-4-turbo', 'claude-3-opus', None for mock)"""
    
    # Aggregated counters
    total_attempts = Column(Integer, default=0, nullable=False)
    """Total number of inference attempts (including failures)"""
    
    total_tokens_prompt = Column(Integer, default=0, nullable=False)
    """Total prompt tokens consumed"""
    
    total_tokens_completion = Column(Integer, default=0, nullable=False)
    """Total completion tokens consumed"""
    
    total_cost_usd = Column(Numeric(10, 6), default=0.0, nullable=False)
    """Total USD cost for this date/provider/model"""
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    """First attempt timestamp"""
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    """Last attempt timestamp"""
    
    # Composite unique constraint: one row per (date, provider, model)
    __table_args__ = (
        Index('idx_budget_date_provider', 'date', 'provider', 'model', unique=True),
    )
    
    def __repr__(self):
        return (
            f"<AIBudgetUsage("
            f"date={self.date}, "
            f"provider={self.provider}, "
            f"model={self.model}, "
            f"attempts={self.total_attempts}, "
            f"cost=${self.total_cost_usd:.4f})>"
        )
