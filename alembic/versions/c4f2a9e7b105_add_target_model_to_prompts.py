"""add_target_model_to_prompts

Revision ID: c4f2a9e7b105
Revises: b2f1a4c7d8e9
Create Date: 2026-09-10 12:30:00.000000

Adds a free-form ``target_model`` label to ``prompts`` recording which
destination AI model the enhanced prompt was formatted for (Claude, ChatGPT,
Midjourney, ...). Persisting it lets the history/vault views show the real
target instead of a hardcoded fallback, and lets re-enhance recover the model
the user originally selected.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4f2a9e7b105'
down_revision: Union[str, None] = 'b2f1a4c7d8e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent add: the column may already exist in databases created directly
    # from the SQLModel metadata before this migration was introduced.
    op.execute(
        "ALTER TABLE prompts "
        "ADD COLUMN IF NOT EXISTS target_model VARCHAR(100)"
    )


def downgrade() -> None:
    with op.batch_alter_table('prompts', schema=None) as batch_op:
        batch_op.drop_column('target_model')
