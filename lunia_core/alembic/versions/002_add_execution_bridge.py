"""Add execution bridge tables for EPOCH C

Revision ID: 002_add_execution_bridge
Revises: 001_add_proposal_domain
Create Date: 2026-01-18 21:35:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON

# revision identifiers, used by Alembic
revision = '002_add_execution_bridge'
down_revision = '001_add_proposal_domain'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create order_plans table
    op.create_table(
        'order_plans',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('execution_intent_id', sa.String(36), nullable=False),
        sa.Column('plan_hash', sa.String(64), nullable=False, index=True),
        sa.Column('plan_version', sa.Integer(), default=1, nullable=False),
        
        # Order array (JSON)
        sa.Column('orders', SQLITE_JSON, nullable=False),
        
        # Metadata
        sa.Column('total_estimated_cost', sa.Float(), nullable=False),
        sa.Column('estimated_slippage', sa.Float(), nullable=False),
        sa.Column('estimated_market_impact', sa.Float(), nullable=False),
        
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('ttl_seconds', sa.Integer(), default=300, nullable=False),
        
        sa.ForeignKeyConstraint(['execution_intent_id'], ['execution_intents.id']),
    )
    
    op.create_index('ix_order_plans_intent_id', 'order_plans', ['execution_intent_id'])
    op.create_index('ix_order_plans_plan_hash', 'order_plans', ['plan_hash'])
    
    # Create order_executions table
    op.create_table(
        'order_executions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('order_plan_id', sa.String(36), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False),
        
        # Idempotency
        sa.Column('client_order_id', sa.String(128), nullable=False, unique=True, index=True),
        sa.Column('exchange_order_id', sa.String(128), nullable=True, index=True),
        
        # Order details
        sa.Column('symbol', sa.String(32), nullable=False),
        sa.Column('side', sa.String(8), nullable=False),  # BUY | SELL
        sa.Column('order_type', sa.String(16), nullable=False),  # ENTRY | TP1 | SL etc
        sa.Column('order_style', sa.String(16), nullable=False),  # MARKET | LIMIT | STOP_LOSS
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('price', sa.Float(), nullable=True),
        
        # Status
        sa.Column('status', sa.String(32), nullable=False),  # PENDING | SUBMITTED | FILLED | CANCELLED | FAILED
        sa.Column('filled_quantity', sa.Float(), default=0.0, nullable=False),
        sa.Column('average_price', sa.Float(), nullable=True),
        
        # Execution snapshot (governance + market + portfolio at submission time)
        sa.Column('execution_snapshot', SQLITE_JSON, nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.Column('filled_at', sa.DateTime(), nullable=True),
        
        # Exchange response (sanitized, no secrets)
        sa.Column('exchange_response', SQLITE_JSON, nullable=True),
        
        sa.ForeignKeyConstraint(['order_plan_id'], ['order_plans.id']),
    )
    
    op.create_index('ix_order_executions_plan_id', 'order_executions', ['order_plan_id'])
    op.create_index('ix_order_executions_status', 'order_executions', ['status'])
    
    # Create execution_queue table
    op.create_table(
        'execution_queue',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('intent_id', sa.String(36), nullable=False, unique=True, index=True),
        
        # Queue status
        sa.Column('status', sa.String(32), nullable=False),  # PENDING | CLAIMED | PROCESSING | COMPLETED | FAILED
        sa.Column('priority', sa.Integer(), default=5, nullable=False),
        
        # Worker lease
        sa.Column('lease_until', sa.DateTime(), nullable=True),
        sa.Column('worker_id', sa.String(64), nullable=True),
        
        # Retry tracking
        sa.Column('attempts', sa.Integer(), default=0, nullable=False),
        sa.Column('max_attempts', sa.Integer(), default=3, nullable=False),
        sa.Column('last_error_code', sa.String(64), nullable=True),
        sa.Column('last_error_message', sa.Text(), nullable=True),
        
        # Timestamps
        sa.Column('enqueued_at', sa.DateTime(), nullable=False),
        sa.Column('claimed_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        
        sa.ForeignKeyConstraint(['intent_id'], ['execution_intents.id']),
    )
    
    op.create_index('ix_execution_queue_status', 'execution_queue', ['status'])
    op.create_index('ix_execution_queue_priority', 'execution_queue', ['priority', 'enqueued_at'])
    
    # Create execution_audit_events table
    op.create_table(
        'execution_audit_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('event_type', sa.String(64), nullable=False),
        
        # Correlation IDs
        sa.Column('intent_id', sa.String(36), nullable=True),
        sa.Column('order_plan_id', sa.String(36), nullable=True),
        sa.Column('order_execution_id', sa.String(36), nullable=True),
        sa.Column('request_id', sa.String(64), nullable=True),
        sa.Column('job_id', sa.String(64), nullable=True),
        sa.Column('worker_id', sa.String(64), nullable=True),
        
        # Actor
        sa.Column('actor_user_id', sa.Integer(), nullable=True),
        sa.Column('actor_role', sa.String(32), nullable=True),
        
        # Hashes
        sa.Column('plan_hash', sa.String(64), nullable=True),
        sa.Column('intent_hash', sa.String(64), nullable=True),
        
        # Reason codes (machine-readable)
        sa.Column('reason_codes', SQLITE_JSON, nullable=True),
        
        # Event metadata (governance snapshot, market snapshot, etc)
        sa.Column('event_metadata', SQLITE_JSON, nullable=True),
        
        # Human-readable message
        sa.Column('message', sa.Text(), nullable=True),
        
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        
        sa.ForeignKeyConstraint(['intent_id'], ['execution_intents.id']),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id']),
    )
    
    op.create_index('ix_execution_audit_intent_ts', 'execution_audit_events', ['intent_id', 'timestamp'])
    op.create_index('ix_execution_audit_event_type_ts', 'execution_audit_events', ['event_type', 'timestamp'])
    
    # Create worker_heartbeats table
    op.create_table(
        'worker_heartbeats',
        sa.Column('worker_id', sa.String(64), primary_key=True),
        sa.Column('last_heartbeat_at', sa.DateTime(), nullable=False),
        sa.Column('version', sa.String(16), nullable=True),
        sa.Column('hostname', sa.String(128), nullable=True),
    )
    
    # Update execution_intents table with new fields
    op.add_column('execution_intents', sa.Column('execution_params', SQLITE_JSON, nullable=True))
    op.add_column('execution_intents', sa.Column('market_snapshot_at_approval', SQLITE_JSON, nullable=True))
    op.add_column('execution_intents', sa.Column('portfolio_snapshot_at_approval', SQLITE_JSON, nullable=True))
    op.add_column('execution_intents', sa.Column('idempotency_key', sa.String(64), nullable=True, unique=True, index=True))


def downgrade() -> None:
    # Drop execution_intents columns
    op.drop_column('execution_intents', 'idempotency_key')
    op.drop_column('execution_intents', 'portfolio_snapshot_at_approval')
    op.drop_column('execution_intents', 'market_snapshot_at_approval')
    op.drop_column('execution_intents', 'execution_params')
    
    # Drop worker_heartbeats
    op.drop_table('worker_heartbeats')
    
    # Drop execution_audit_events
    op.drop_index('ix_execution_audit_event_type_ts', 'execution_audit_events')
    op.drop_index('ix_execution_audit_intent_ts', 'execution_audit_events')
    op.drop_table('execution_audit_events')
    
    # Drop execution_queue
    op.drop_index('ix_execution_queue_priority', 'execution_queue')
    op.drop_index('ix_execution_queue_status', 'execution_queue')
    op.drop_table('execution_queue')
    
    # Drop order_executions
    op.drop_index('ix_order_executions_status', 'order_executions')
    op.drop_index('ix_order_executions_plan_id', 'order_executions')
    op.drop_table('order_executions')
    
    # Drop order_plans
    op.drop_index('ix_order_plans_plan_hash', 'order_plans')
    op.drop_index('ix_order_plans_intent_id', 'order_plans')
    op.drop_table('order_plans')
