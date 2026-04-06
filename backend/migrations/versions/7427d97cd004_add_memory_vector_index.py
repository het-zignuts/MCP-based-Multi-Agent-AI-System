"""add memory vector index

Revision ID: 7427d97cd004
Revises: 8172e3e4f9ce
Create Date: 2026-03-30 14:42:42.639703

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7427d97cd004'
down_revision: Union[str, Sequence[str], None] = '8172e3e4f9ce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE INDEX memory_embedding_idx
        ON memory
        USING hnsw (embedding vector_l2_ops)
    """)


def downgrade() -> None:
    """Downgrade schema."""
    pass
