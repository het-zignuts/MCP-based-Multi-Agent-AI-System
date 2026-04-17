"""Add profile items to user profile snapshot

Revision ID: 4f6e1c2b7d91
Revises: c96bd23576a3
Create Date: 2026-04-15 18:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4f6e1c2b7d91"
down_revision: Union[str, Sequence[str], None] = "c96bd23576a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column(
        "user_profile_snapshot",
        sa.Column(
            "profile_items",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )


def downgrade():
    op.drop_column("user_profile_snapshot", "profile_items")
