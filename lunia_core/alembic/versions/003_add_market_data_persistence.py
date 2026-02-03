"""003_add_market_data_persistence

Revision ID: 003_add_market_data_persistence
Revises: 002_add_execution_bridge
Create Date: 2026-01-19

EPOCH D Phase D2: Market Data Persistence
- Creates market_candles table for historical OHLCV storage
- Enforces idempotency via UNIQUE constraint
- Adds composite index for efficient queries
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003_add_market_data_persistence'
down_revision = '002_add_execution_bridge'
branch_labels = None
depends_on = None


def upgrade():
    """Create market_candles table"""
    op.create_table(
        'market_candles',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('exchange', sa.String(length=50), nullable=False),
        sa.Column('symbol', sa.String(length=50), nullable=False),
        sa.Column('timeframe', sa.String(length=10), nullable=False),
        sa.Column('timestamp_ms', sa.BigInteger(), nullable=False),
        sa.Column('open', sa.Float(), nullable=False),
        sa.Column('high', sa.Float(), nullable=False),
        sa.Column('low', sa.Float(), nullable=False),
        sa.Column('close', sa.Float(), nullable=False),
        sa.Column('volume', sa.Float(), nullable=False),
        sa.Column('received_at_ms', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('exchange', 'symbol', 'timeframe', 'timestamp_ms', name='uq_candle_identity')
    )
    
    # Create indexes
    op.create_index('idx_candle_query', 'market_candles', ['exchange', 'symbol', 'timeframe', 'timestamp_ms'], unique=False)
    op.create_index(op.f('ix_market_candles_exchange'), 'market_candles', ['exchange'], unique=False)
    op.create_index(op.f('ix_market_candles_symbol'), 'market_candles', ['symbol'], unique=False)
    op.create_index(op.f('ix_market_candles_timeframe'), 'market_candles', ['timeframe'], unique=False)
    op.create_index(op.f('ix_market_candles_timestamp_ms'), 'market_candles', ['timestamp_ms'], unique=False)


def downgrade():
    """Drop market_candles table"""
    op.drop_index(op.f('ix_market_candles_timestamp_ms'), table_name='market_candles')
    op.drop_index(op.f('ix_market_candles_timeframe'), table_name='market_candles')
    op.drop_index(op.f('ix_market_candles_symbol'), table_name='market_candles')
    op.drop_index(op.f('ix_market_candles_exchange'), table_name='market_candles')
    op.drop_index('idx_candle_query', table_name='market_candles')
    op.drop_table('market_candles')
