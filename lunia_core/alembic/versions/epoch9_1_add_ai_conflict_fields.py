"""Epoch 9.1: Add AI conflict detection fields

Phase: Epoch 9.1 - Strategy Intelligence Pack
Purpose: Add structured conflict detection fields to ai_analysis table

New columns:
- ai_agrees_with_core: Boolean (nullable)
- conflict_reason_code: String(50) - Enum classification
- conflict_severity: String(20) - Severity level
- conflict_explanation: Text - Detailed explanation

Revision ID: 007_add_ai_conflict_fields
Revises: 006_add_market_state
Create Date: 2026-02-04 
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '007_add_ai_conflict_fields'
down_revision: Union[str, None] = '006_add_market_state'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add Epoch 9.1 conflict detection fields to ai_analysis table.
    
    All fields nullable to support backward compatibility and graceful rollout.
    """
    # Add ai_agrees_with_core (boolean, nullable)
    op.add_column(
        'ai_analysis',
        sa.Column('ai_agrees_with_core', sa.Boolean(), nullable=True)
    )
    
    # Add conflict_reason_code (string enum, nullable)
    op.add_column(
        'ai_analysis',
        sa.Column('conflict_reason_code', sa.String(length=50), nullable=True)
    )
    
    # Add conflict_severity (string enum, nullable)
    op.add_column(
        'ai_analysis',
        sa.Column('conflict_severity', sa.String(length=20), nullable=True)
    )
    
    # Add conflict_explanation (text, nullable)
    op.add_column(
        'ai_analysis',
        sa.Column('conflict_explanation', sa.Text(), nullable=True)
    )
    
    # Optional: Add index for conflict queries
    op.create_index(
        'ix_ai_analysis_conflict_severity',
        'ai_analysis',
        ['conflict_severity', 'created_at'],
        unique=False
    )


def downgrade() -> None:
    """Remove Epoch 9.1 conflict detection fields"""
    
    # Drop index first
    op.drop_index('ix_ai_analysis_conflict_severity', table_name='ai_analysis')
    
    # Drop columns
    op.drop_column('ai_analysis', 'conflict_explanation')
    op.drop_column('ai_analysis', 'conflict_severity')
    op.drop_column('ai_analysis', 'conflict_reason_code')
    op.drop_column('ai_analysis', 'ai_agrees_with_core')
