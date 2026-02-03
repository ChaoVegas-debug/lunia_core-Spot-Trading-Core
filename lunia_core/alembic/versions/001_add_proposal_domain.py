"""Add proposal domain tables for EPOCH B

Revision ID: 001_add_proposal_domain
Revises: 
Create Date: 2026-01-18 20:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON

# revision identifiers, used by Alembic
revision = '001_add_proposal_domain'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create proposals table
    op.create_table(
        'proposals',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(32), nullable=False),
        
        # Classification
        sa.Column('asset', sa.String(32), nullable=False),
        sa.Column('action', sa.String(16), nullable=False),
        sa.Column('horizon', sa.String(16), nullable=False),
        sa.Column('risk_label', sa.String(16), nullable=False),
        sa.Column('priority_score', sa.Integer(), nullable=False),
        
        # Governance snapshot (IMMUTABLE)
        sa.Column('governance_snapshot', SQLITE_JSON, nullable=False),
        
        # Thesis
        sa.Column('thesis_summary', sa.Text(), nullable=False),
        sa.Column('thesis_dna', SQLITE_JSON, nullable=False),
        sa.Column('invalidation_rules', SQLITE_JSON, nullable=True),
        
        # Evidence
        sa.Column('factor_attribution', SQLITE_JSON, nullable=False),
        sa.Column('model_votes', SQLITE_JSON, nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('devils_advocate', sa.Text(), nullable=False),
        
        # Execution plan preview
        sa.Column('execution_plan_preview', SQLITE_JSON, nullable=True),
        
        # Lifecycle
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('supersedes_id', sa.String(36), nullable=True),
        
        # Actors
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('approved_by_user_id', sa.Integer(), nullable=True),
        sa.Column('rejected_by_user_id', sa.Integer(), nullable=True),
        
        # Event timestamps
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('rejected_at', sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sa.String(255), nullable=True),
        
        sa.ForeignKeyConstraint(['supersedes_id'], ['proposals.id']),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['approved_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['rejected_by_user_id'], ['users.id']),
    )
    
    # Create indexes for proposals
    op.create_index('ix_proposal_status_asset_created', 'proposals', ['status', 'asset', 'created_at'])
    op.create_index('ix_proposal_version_id', 'proposals', ['id', 'version'])
    
    # Create execution_intents table
    op.create_table(
        'execution_intents',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('proposal_id', sa.String(36), nullable=False),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('plan_snapshot', SQLITE_JSON, nullable=False),
        sa.Column('governance_snapshot_at_approval', SQLITE_JSON, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        
        sa.ForeignKeyConstraint(['proposal_id'], ['proposals.id']),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
    )
    
    op.create_index('ix_execution_intents_proposal_id', 'execution_intents', ['proposal_id'])
    
    # Create proposal_audit_events table
    op.create_table(
        'proposal_audit_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('proposal_id', sa.String(36), nullable=False),
        sa.Column('event_type', sa.String(64), nullable=False),
        sa.Column('actor_user_id', sa.Integer(), nullable=True),
        sa.Column('actor_role', sa.String(32), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('governance_snapshot', SQLITE_JSON, nullable=False),
        sa.Column('confidence_score_at_decision', sa.Float(), nullable=True),
        sa.Column('data_freshness_state_at_decision', sa.String(16), nullable=True),
        sa.Column('event_metadata', SQLITE_JSON, nullable=True),
        
        sa.ForeignKeyConstraint(['proposal_id'], ['proposals.id']),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id']),
    )
    
    op.create_index('ix_proposal_audit_proposal_ts', 'proposal_audit_events', ['proposal_id', 'timestamp'])
    op.create_index('ix_proposal_audit_event_type_ts', 'proposal_audit_events', ['event_type', 'timestamp'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_proposal_audit_event_type_ts', 'proposal_audit_events')
    op.drop_index('ix_proposal_audit_proposal_ts', 'proposal_audit_events')
    op.drop_table('proposal_audit_events')
    
    op.drop_index('ix_execution_intents_proposal_id', 'execution_intents')
    op.drop_table('execution_intents')
    
    op.drop_index('ix_proposal_version_id', 'proposals')
    op.drop_index('ix_proposal_status_asset_created', 'proposals')
    op.drop_table('proposals')
