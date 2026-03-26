"""add vector index

Revision ID: e4ec87f109f1
Revises: 2f7fda260737
Create Date: 2026-03-25 11:51:39.343860

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4ec87f109f1'
down_revision: Union[str, Sequence[str], None] = '2f7fda260737'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.execute("""
    CREATE INDEX IF NOT EXISTS chunk_embedding_idx
    ON chunk
    USING hnsw (embedding vector_cosine_ops);
    """)


def downgrade() -> None:
    op.execute("""
    DROP INDEX IF EXISTS chunk_embedding_idx;
    """)
