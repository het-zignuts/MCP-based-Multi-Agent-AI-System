"""Fixed metadata column name

Revision ID: 6190823fd0cf
Revises: fix_memory_table_schema
Create Date: 2026-03-30 16:13:35.460598

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
from typing import Sequence, Union

from alembic import op


revision: str = "6190823fd0cf"
down_revision: Union[str, Sequence[str], None] = "fix_memory_table_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "memory",
        "metadata",
        new_column_name="memory_metadata",
    )


def downgrade() -> None:
    op.alter_column(
        "memory",
        "memory_metadata",
        new_column_name="metadata",
    )
