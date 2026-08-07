"""add google oauth fields to users

Revision ID: 7f3c6d4b2a11
Revises: 3f8a92b10c5d
Create Date: 2026-08-07 12:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7f3c6d4b2a11'
down_revision: Union[str, None] = '3f8a92b10c5d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = {col['name'] for col in inspector.get_columns('users')}

    with op.batch_alter_table('users', schema=None) as batch_op:
        if 'auth_provider' not in columns:
            batch_op.add_column(
                sa.Column('auth_provider', sa.String(length=50), nullable=False, server_default=sa.text("'local'"))
            )
        if 'google_sub' not in columns:
            batch_op.add_column(sa.Column('google_sub', sa.String(length=255), nullable=True))

    indexes = {index['name'] for index in inspector.get_indexes('users')}
    if 'ix_users_google_sub' not in indexes:
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.create_index('ix_users_google_sub', ['google_sub'], unique=True)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = {col['name'] for col in inspector.get_columns('users')}
    indexes = {index['name'] for index in inspector.get_indexes('users')}

    with op.batch_alter_table('users', schema=None) as batch_op:
        if 'ix_users_google_sub' in indexes:
            batch_op.drop_index('ix_users_google_sub')
        if 'google_sub' in columns:
            batch_op.drop_column('google_sub')
        if 'auth_provider' in columns:
            batch_op.drop_column('auth_provider')
