"""
Alembic environment configuration for LUNIA/ALADDIN
EPOCH B: Proposal Domain Migration
"""
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Import Base from auth.database (includes all models)
from lunia_core.app.services.auth.database import Base, DATABASE_URL

# Import proposal models to ensure they're registered
from lunia_core.app.services.proposal.models import Proposal, ExecutionIntent, ProposalAuditEvent

# Import execution journal models (Phase 7)
from lunia_core.app.services.execution_journal.models import SignalEvent, AIAnalysis, AIInferenceLog

# Import budget tracking model (Phase 8.0)
from lunia_core.app.services.execution_journal.budget_model import AIBudgetUsage

# Alembic Config object
config = context.config

# Override sqlalchemy.url with DATABASE_URL from environment
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
