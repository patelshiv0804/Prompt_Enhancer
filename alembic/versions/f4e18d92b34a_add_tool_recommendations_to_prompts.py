"""add_tool_recommendations_to_prompts

Revision ID: f4e18d92b34a
Revises: e3328e132a21
Create Date: 2026-08-07 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f4e18d92b34a'
down_revision: Union[str, None] = 'e3328e132a21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('prompts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tool_recommendations', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('prompts', schema=None) as batch_op:
        batch_op.drop_column('tool_recommendations')
