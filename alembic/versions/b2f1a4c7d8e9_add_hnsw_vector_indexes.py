"""add HNSW vector indexes on templates.embedding and prompts.embedding

Adds approximate-nearest-neighbour indexes so semantic retrieval uses an index
scan instead of a full-table sequential scan plus per-row cosine math. Both the
template search (app/repositories/template.py) and the prompt duplicate/search
path (app/repositories/prompt.py) order by ``embedding.cosine_distance(...)``,
which maps to the ``vector_cosine_ops`` operator class.

HNSW is chosen over IVFFLAT: it needs no training / ``lists`` tuning, stays
accurate as rows are added, and gives better recall/latency at this dataset
size. It requires pgvector >= 0.5.0. If the deployed pgvector is older, swap the
CREATE INDEX statements for the IVFFLAT variants noted in the comments below.

Dimensions are unchanged (Vector(384)); indexes are created IF NOT EXISTS so
this is safe to run even if app.db.session.ensure_vector_indexes() (the startup
safety net, which uses the same index names) already created them.

Revision ID: b2f1a4c7d8e9
Revises: d7e8f9a0b1c2
Create Date: 2026-08-26 00:00:00.000000
"""
from alembic import op

revision = "b2f1a4c7d8e9"
down_revision = "d7e8f9a0b1c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NOTE: CREATE INDEX (without CONCURRENTLY) takes an ACCESS EXCLUSIVE lock
    # for the duration of the build. These tables are small, so the build is
    # quick; run during a maintenance window if a table has grown large.
    # CONCURRENTLY is intentionally NOT used because Alembic wraps each migration
    # in a transaction and CREATE INDEX CONCURRENTLY cannot run in one.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_templates_embedding_hnsw "
        "ON templates USING hnsw (embedding vector_cosine_ops);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_prompts_embedding_hnsw "
        "ON prompts USING hnsw (embedding vector_cosine_ops);"
    )
    # IVFFLAT fallback for pgvector < 0.5.0 (needs data present at build time and
    # a tuned `lists` value; run ANALYZE afterwards):
    #   CREATE INDEX IF NOT EXISTS ix_templates_embedding_ivfflat
    #     ON templates USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
    #   CREATE INDEX IF NOT EXISTS ix_prompts_embedding_ivfflat
    #     ON prompts USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_prompts_embedding_hnsw;")
    op.execute("DROP INDEX IF EXISTS ix_templates_embedding_hnsw;")
