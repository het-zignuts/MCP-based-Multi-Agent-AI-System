from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers
revision: str = '2f7fda260737'
down_revision: Union[str, Sequence[str], None] = '8a51062bf617'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # enable pgvector
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # create chunk table
    op.create_table(
        "chunk",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("file_id", sa.Uuid(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("embedding", Vector(384), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("chunk")