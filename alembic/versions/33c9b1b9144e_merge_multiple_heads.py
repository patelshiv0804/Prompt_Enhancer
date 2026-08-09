"""Merge multiple heads

Revision ID: 33c9b1b9144e
Revises: 9614bbfec30b, a1b2c3d4e5f6
Create Date: 2026-08-09 05:46:08.308954

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '33c9b1b9144e'
down_revision: Union[str, None] = ('9614bbfec30b', 'a1b2c3d4e5f6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
