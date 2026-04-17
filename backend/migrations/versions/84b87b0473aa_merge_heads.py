"""merge heads

Revision ID: 84b87b0473aa
Revises: 4f6e1c2b7d91, 971acdcdd25c
Create Date: 2026-04-15 17:21:22.692528

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '84b87b0473aa'
down_revision: Union[str, Sequence[str], None] = ('4f6e1c2b7d91', '971acdcdd25c')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
