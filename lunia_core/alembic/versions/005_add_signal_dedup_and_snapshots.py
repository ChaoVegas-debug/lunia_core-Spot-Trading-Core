"""Phase 8.2A: Add signal deduplication and context snapshots

Revision ID: 005_add_signal_dedup_and_snapshots
Revises: 004_add_execution_journal
Create Date: 2026-02-04 16:00:00

Purpose: Enable intent persistence with deduplication and multi-level context snapshotting.
This is additive-only; all existing signal_events data remains intact.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON

# revision identifiers, used by Alembic
revision = '005_add_signal_dedup_and_snapshots'
down_revision = '004_add_execution_journal'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add deduplication columns
    op.add_column('signal_events', sa.Column('dedup_key', sa.String(255), nullable=True))
    op.add_column('signal_events', sa.Column('timestamp_bucket', sa.Integer(), nullable=True))
    
    # Add context snapshot columns (L1/L2/L3)
    op.add_column('signal_events', sa.Column('context_snapshot', SQLITE_JSON, nullable=True))
    op.add_column('signal_events', sa.Column('snapshot_truncated', sa.Boolean(), default=False, nullable=True))
    op.add_column('signal_events', sa.Column('snapshot_level', sa.String(10), nullable=True))
    
    # Add indexes for efficient queries
    op.create_index('ix_signal_events_dedup_key', 'signal_events', ['dedup_key'])
    op.create_index('ix_signal_events_timestamp_bucket', 'signal_events', ['timestamp_bucket'])
    
    # Composite index for dedup queries (strategy + symbol + bucket)
    op.create_index(
        'ix_signal_dedup_lookup',
        'signal_events',
        ['strategy_id', 'symbol', 'timestamp_bucket']
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_signal_dedup_lookup', 'signal_events')
    op.drop_index('ix_signal_events_timestamp_bucket', 'signal_events')
    op.drop_index('ix_signal_events_dedup_key', 'signal_events')
    
    # Drop columns
    op.drop_column('signal_events', 'snapshot_level')
    op.drop_column('signal_events', 'snapshot_truncated')
    op.drop_column('signal_events', 'context_snapshot')
    op.drop_column('signal_events', 'timestamp_bucket')
    op.drop_column('signal_events', 'dedup_key')
