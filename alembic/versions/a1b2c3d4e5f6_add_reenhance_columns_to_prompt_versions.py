"""add_reenhance_columns_to_prompt_versions

Revision ID: a1b2c3d4e5f6
Revises: af3e6b17c00b
Create Date: 2026-08-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'a1b2c3d4e5f6'
down_revision = 'af3e6b17c00b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'prompt_versions',
        sa.Column('old_analysis', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        'prompt_versions',
        sa.Column('new_analysis', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        'prompt_versions',
        sa.Column('tool_recommendations', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        'prompt_versions',
        sa.Column(
            'template_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('templates.id', ondelete='SET NULL'),
            nullable=True,
        ),
    )
    op.create_index(
        'ix_prompt_versions_template_id',
        'prompt_versions',
        ['template_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_prompt_versions_template_id', table_name='prompt_versions')
    op.drop_column('prompt_versions', 'template_id')
    op.drop_column('prompt_versions', 'tool_recommendations')
    op.drop_column('prompt_versions', 'new_analysis')
    op.drop_column('prompt_versions', 'old_analysis')
