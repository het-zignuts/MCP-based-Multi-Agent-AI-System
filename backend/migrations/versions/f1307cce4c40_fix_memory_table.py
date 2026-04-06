"""fix memory table schema

Revision ID: fix_memory_table_schema
Revises: 7427d97cd004
Create Date: 2026-03-30 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "fix_memory_table_schema"
down_revision: Union[str, Sequence[str], None] = "7427d97cd004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename metadata -> metadata only if old column exists under a different name in your app usage.
    # Since your migration already created "metadata", we keep it and align the table shape.

    op.add_column(
        "memory",
        sa.Column("importance_score", sa.Float(), nullable=False, server_default="0.5"),
    )
    op.add_column(
        "memory",
        sa.Column("source", sa.String(), nullable=False, server_default="conversation"),
    )
    op.add_column(
        "memory",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "memory",
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.add_column(
        "memory",
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )

    op.create_index("ix_memory_memory_type", "memory", ["memory_type"], unique=False)

    # Make metadata non-null and backfill existing null rows
    op.execute("UPDATE memory SET metadata = '{}'::json WHERE metadata IS NULL")
    op.alter_column(
        "memory",
        "metadata",
        existing_type=sa.JSON(),
        nullable=False,
    )

    # Drop server defaults after backfill so app code controls values
    op.alter_column("memory", "importance_score", server_default=None)
    op.alter_column("memory", "source", server_default=None)
    op.alter_column("memory", "is_active", server_default=None)
    op.alter_column("memory", "created_at", server_default=None)
    op.alter_column("memory", "updated_at", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_memory_memory_type", table_name="memory")
    op.drop_column("memory", "updated_at")
    op.drop_column("memory", "created_at")
    op.drop_column("memory", "is_active")
    op.drop_column("memory", "source")
    op.drop_column("memory", "importance_score")
