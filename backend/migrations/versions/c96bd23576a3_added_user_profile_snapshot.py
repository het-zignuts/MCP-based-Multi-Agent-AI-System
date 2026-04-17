"""Added user profile snapshot

Revision ID: c96bd23576a3
Revises: 6190823fd0cf
Create Date: 2026-04-08 11:57:48.812460

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c96bd23576a3'
down_revision: Union[str, Sequence[str], None] = '6190823fd0cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        "user_profile_snapshot",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_text", sa.Text(), nullable=False),
        sa.Column("preferences", sa.JSON(), nullable=False),
        sa.Column("facts", sa.JSON(), nullable=False),
        sa.Column("active_goals", sa.JSON(), nullable=False),
        sa.Column("decisions", sa.JSON(), nullable=False),
        sa.Column("source_memory_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(
        "ix_user_profile_snapshot_user_id",
        "user_profile_snapshot",
        ["user_id"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_user_profile_snapshot_user_id", table_name="user_profile_snapshot")
    op.drop_table("user_profile_snapshot")
    # ### end Alembic commands ###
