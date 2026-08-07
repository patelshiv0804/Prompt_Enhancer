"""merge multiple heads

Revision ID: af3e6b17c00b
Revises: 7f3c6d4b2a11, f4e18d92b34a
Create Date: 2026-08-07 17:00:17.458748

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'af3e6b17c00b'
down_revision: Union[str, None] = ('7f3c6d4b2a11', 'f4e18d92b34a')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
