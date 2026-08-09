"""clean remaining markdown formatting from prompt versions

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
Create Date: 2026-08-09
"""

from alembic import op


revision = "d7e8f9a0b1c2"
down_revision = "c6d7e8f9a0b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove remaining inline emphasis, Markdown heading prefixes, and visual
    # separators while retaining all prompt wording and line structure.
    op.execute(
        r"""
        UPDATE prompt_versions
        SET content = regexp_replace(
            regexp_replace(
                regexp_replace(
                    regexp_replace(content, E'\\*([^*\\n]+)\\*', E'\\1', 'g'),
                    E'(^|\\n)[[:space:]]*#{1,6}[[:space:]]*', E'\\1', 'g'
                ),
                E'(^|\\n)[[:space:]]*(---+|___+)[[:space:]]*($|\\n)', E'\\1', 'g'
            ),
            E'\\n{3,}', E'\\n\\n', 'g'
        )
        WHERE content ~ E'\\*|(^|\\n)[[:space:]]*#{1,6}[[:space:]]|---+'
        """
    )


def downgrade() -> None:
    pass
