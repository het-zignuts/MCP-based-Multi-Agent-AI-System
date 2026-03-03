# migrations/env.py
from logging.config import fileConfig
import asyncio

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context
from sqlmodel import SQLModel
from app.db.models import User, Conversation, Message, File
from app.core.config import settings  # your Pydantic settings

# Alembic Config object
config = context.config

# Logging setup from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata for autogenerate
target_metadata = SQLModel.metadata

# ---------------------------
# Offline migrations (sync)
# ---------------------------
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------
# Online migrations (async)
# ---------------------------
async def do_run_migrations_online():
    """Async migrations using SQLAlchemy async engine."""
    connectable = create_async_engine(
        settings.DATABASE_URL,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        # Configure context with the connection
        await connection.run_sync(
            lambda conn: context.configure(connection=conn, target_metadata=target_metadata)
        )
        # Run migrations safely
        await connection.run_sync(lambda conn: context.run_migrations())

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online mode."""
    asyncio.run(do_run_migrations_online())


# ---------------------------
# Decide which mode to run
# ---------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()