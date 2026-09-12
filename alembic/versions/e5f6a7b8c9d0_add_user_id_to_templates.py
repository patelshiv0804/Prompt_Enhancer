"""add_user_id_to_templates

Revision ID: e5f6a7b8c9d0
Revises: c4f2a9e7b105
Create Date: 2026-09-12 12:30:00.000000

Adds a nullable `user_id` column to `templates` referencing `profiles.id`
(ON DELETE CASCADE), with an index.
Templates with user_id NULL represent system/curated templates, while
templates with user_id set represent custom templates created by that user.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'c4f2a9e7b105'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE templates "
        "ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES profiles(id) ON DELETE CASCADE"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_templates_user_id ON templates (user_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_templates_user_id")
    op.execute("ALTER TABLE templates DROP COLUMN IF EXISTS user_id")
