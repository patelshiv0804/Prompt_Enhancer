"""add role to profiles table

Revision ID: 3f8a92b10c5d
Revises: 0a1c19d7a985
Create Date: 2026-08-07 10:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f8a92b10c5d'
down_revision: Union[str, None] = '0a1c19d7a985'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('profiles')]
    if 'role' not in columns:
        with op.batch_alter_table('profiles', schema=None) as batch_op:
            batch_op.add_column(sa.Column('role', sa.String(length=100), nullable=True, server_default=sa.text("'creator'")))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('profiles')]
    if 'role' in columns:
        with op.batch_alter_table('profiles', schema=None) as batch_op:
            batch_op.drop_column('role')
