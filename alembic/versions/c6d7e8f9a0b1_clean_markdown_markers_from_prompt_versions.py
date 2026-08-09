"""clean markdown markers from stored prompt versions

Revision ID: c6d7e8f9a0b1
Revises: 33c9b1b9144e
Create Date: 2026-08-09
"""

from alembic import op


revision = "c6d7e8f9a0b1"
down_revision = "33c9b1b9144e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing LLM output sometimes used Markdown emphasis. Version content is
    # stored as plain prompt text, so remove the formatting delimiters while
    # retaining the actual prompt wording.
    op.execute(
        """
        UPDATE prompt_versions
        SET content = replace(replace(replace(content, '**', ''), '__', ''), '`', '')
        WHERE content LIKE '%**%' OR content LIKE '%__%' OR content LIKE '%`%'
        """
    )


def downgrade() -> None:
    # The removed formatting delimiters cannot be reconstructed safely.
    pass
