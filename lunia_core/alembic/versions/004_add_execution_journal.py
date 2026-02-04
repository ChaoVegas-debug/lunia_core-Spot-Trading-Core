"""Phase 7: create execution journal tables (signal_events, ai_analysis, ai_inference_logs)

Revision ID: 004_add_execution_journal
Revises: 003_add_market_data_persistence
Create Date: 2026-02-04 11:40:00

Purpose: Execution Journal for making deterministic signal intelligence legible and auditable.
This is NOT adding intelligence - it's revealing existing intelligence via structured persistence.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON

# revision identifiers, used by Alembic
revision = '004_add_execution_journal'
down_revision = '003_add_market_data_persistence'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create signal_events table (Deterministic signal capture)
    op.create_table(
        'signal_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('strategy_id', sa.String(255), nullable=False),
        sa.Column('symbol', sa.String(50), nullable=False),
        sa.Column('signal_type', sa.String(16), nullable=False),  # BUY, SELL, HOLD, EXIT
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('market_context', SQLITE_JSON, nullable=True),
        sa.Column('risk_filters_applied', SQLITE_JSON, nullable=True),
        sa.Column('deterministic_reasoning', sa.Text(), nullable=True),
    )
    
    # Create indexes for signal_events
    op.create_index('ix_signal_events_strategy_id', 'signal_events', ['strategy_id'])
    op.create_index('ix_signal_events_symbol', 'signal_events', ['symbol'])
    op.create_index('ix_signal_events_timestamp', 'signal_events', ['timestamp'])
    op.create_index('ix_signal_strategy_timestamp', 'signal_events', ['strategy_id', 'timestamp'])
    op.create_index('ix_signal_symbol_timestamp', 'signal_events', ['symbol', 'timestamp'])
    op.create_index('ix_signal_type_timestamp', 'signal_events', ['signal_type', 'timestamp'])
    
    # Create ai_analysis table (Synthetic reasoning layer)
    op.create_table(
        'ai_analysis',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('signal_event_id', sa.String(36), nullable=False),
        sa.Column('model_revision', sa.String(255), nullable=False),
        sa.Column('reasoning_version', sa.String(50), nullable=True),
        sa.Column('ai_constitution_hash', sa.String(64), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('risk_flags', SQLITE_JSON, nullable=True),
        sa.Column('confirmation', sa.Boolean(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('confidence_reason', sa.Text(), nullable=True),
        sa.Column('conflicts_with_core', sa.Boolean(), nullable=False),
        sa.Column('conflict_reason', sa.Text(), nullable=True),
        sa.Column('invalid_if', SQLITE_JSON, nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('cost_usd', sa.Numeric(10, 6), nullable=True),
        sa.Column('operator_feedback', sa.String(20), nullable=True),
        sa.Column('feedback_comment', sa.Text(), nullable=True),
        sa.Column('feedback_timestamp', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        
        sa.ForeignKeyConstraint(['signal_event_id'], ['signal_events.id']),
        sa.UniqueConstraint('signal_event_id', name='uq_ai_analysis_signal_event'),
    )
    
    # Create indexes for ai_analysis
    op.create_index('ix_ai_analysis_signal_event_id', 'ai_analysis', ['signal_event_id'])
    op.create_index('ix_ai_analysis_created', 'ai_analysis', ['created_at'])
    op.create_index('ix_ai_analysis_conflicts', 'ai_analysis', ['conflicts_with_core'])
    
    # Create ai_inference_logs table (Immutable audit trail)
    op.create_table(
        'ai_inference_logs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('context_snapshot', SQLITE_JSON, nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), nullable=True),
        sa.Column('completion_tokens', sa.Integer(), nullable=True),
        sa.Column('total_cost_usd', sa.Numeric(10, 6), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('provider', sa.String(50), nullable=True),
        sa.Column('model_name', sa.String(255), nullable=True),
        sa.Column('response_valid', sa.Boolean(), nullable=True),
        sa.Column('validation_error', sa.Text(), nullable=True),
        sa.Column('shadow_mode', sa.Boolean(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
    )
    
    # Create indexes for ai_inference_logs
    op.create_index('ix_ai_inference_logs_event_type', 'ai_inference_logs', ['event_type'])
    op.create_index('ix_ai_inference_timestamp', 'ai_inference_logs', ['timestamp'])
    op.create_index('ix_ai_inference_shadow', 'ai_inference_logs', ['shadow_mode', 'timestamp'])
    op.create_index('ix_ai_inference_provider', 'ai_inference_logs', ['provider', 'timestamp'])


def downgrade() -> None:
    # Drop ai_inference_logs table
    op.drop_index('ix_ai_inference_provider', 'ai_inference_logs')
    op.drop_index('ix_ai_inference_shadow', 'ai_inference_logs')
    op.drop_index('ix_ai_inference_timestamp', 'ai_inference_logs')
    op.drop_index('ix_ai_inference_logs_event_type', 'ai_inference_logs')
    op.drop_table('ai_inference_logs')
    
    # Drop ai_analysis table
    op.drop_index('ix_ai_analysis_conflicts', 'ai_analysis')
    op.drop_index('ix_ai_analysis_created', 'ai_analysis')
    op.drop_index('ix_ai_analysis_signal_event_id', 'ai_analysis')
    op.drop_table('ai_analysis')
    
    # Drop signal_events table
    op.drop_index('ix_signal_type_timestamp', 'signal_events')
    op.drop_index('ix_signal_symbol_timestamp', 'signal_events')
    op.drop_index('ix_signal_strategy_timestamp', 'signal_events')
    op.drop_index('ix_signal_events_timestamp', 'signal_events')
    op.drop_index('ix_signal_events_symbol', 'signal_events')
    op.drop_index('ix_signal_events_strategy_id', 'signal_events')
    op.drop_table('signal_events')
