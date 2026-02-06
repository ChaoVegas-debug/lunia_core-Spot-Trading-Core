"""Phase 8.3-Integration: Add market_state to signal_events

Revision ID: 006_add_market_state
Revises: 005_add_signal_dedup_and_snapshots
Create Date: 2026-02-04 17:55:00

Purpose: Add market enrichment context to signal events for AI analysis.
Provides deterministic market physics (volume, volatility, regime, liquidity) as read-only context.
This is additive-only; all existing signal_events data remains intact.

Dialect Safety: Uses JSON (SQLite-compatible) as base, with JSONB for PostgreSQL production.
"""
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic
revision = '006_add_market_state'
down_revision = '005_add_signal_dedup_and_snapshots'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add market_state column with dialect-aware JSON/JSONB handling
    
    - SQLite (tests): JSON type
    - PostgreSQL (production): JSONB with GIN index
    """
    # Dialect-safe column type (matches models.py)
    column_type = sa.JSON().with_variant(JSONB, "postgresql")
    
    # Add nullable market_state column
    op.add_column('signal_events', sa.Column('market_state', column_type, nullable=True))
    
    # PostgreSQL-specific: add GIN index for JSONB querying
    # Note: This will only execute on PostgreSQL due to postgresql_using parameter
    conn = op.get_bind()
    if conn.dialect.name == 'postgresql':
        op.create_index(
            'ix_signal_events_market_state_gin',
            'signal_events',
            ['market_state'],
            postgresql_using='gin'
        )


def downgrade() -> None:
    """
    Reversible: drop market_state column and index
    """
    conn = op.get_bind()
    dialect = conn.dialect.name
    
    # Drop index if PostgreSQL
    if dialect == 'postgresql':
        op.drop_index('ix_signal_events_market_state_gin', 'signal_events')
    
    # Drop column
    op.drop_column('signal_events', 'market_state')
