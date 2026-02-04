"""
Add AI Budget Tracking Table

Revision ID: 005
Revises: 004
Create Date: 2026-02-04

This migration adds the ai_budget_usage table for persistent AI budget tracking.

CRITICAL:
Budget state MUST survive backend restarts.
This table is the source of truth for daily AI spend.
"""

from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    """
    Create ai_budget_usage table for persistent budget tracking.
    """
    op.create_table(
        'ai_budget_usage',
        
        # Primary key
        sa.Column('id', sa.String(36), primary_key=True),
        
        # Partition key: UTC calendar day
        sa.Column('date', sa.Date(), nullable=False),
        
        # Provider and model
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('model', sa.String(100), nullable=True),
        
        # Aggregated counters
        sa.Column('total_attempts', sa.Integer(), default=0, nullable=False),
        sa.Column('total_tokens_prompt', sa.Integer(), default=0, nullable=False),
        sa.Column('total_tokens_completion', sa.Integer(), default=0, nullable=False),
        sa.Column('total_cost_usd', sa.Numeric(10, 6), default=0.0, nullable=False),
        
        # Metadata
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow, nullable=False),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, nullable=False)
    )
    
    # Index for date lookup (very common query: "get today's spend")
    op.create_index(
        'idx_budget_date',
        'ai_budget_usage',
        ['date']
    )
    
    # Composite unique index for (date, provider, model)
    # Ensures one row per combination
    op.create_index(
        'idx_budget_date_provider',
        'ai_budget_usage',
        ['date', 'provider', 'model'],
        unique=True
    )
    
    print("✅ Created ai_budget_usage table with 2 indexes")


def downgrade():
    """
    Drop ai_budget_usage table and indexes.
    """
    op.drop_index('idx_budget_date_provider', table_name='ai_budget_usage')
    op.drop_index('idx_budget_date', table_name='ai_budget_usage')
    op.drop_table('ai_budget_usage')
    
    print("✅ Dropped ai_budget_usage table")
