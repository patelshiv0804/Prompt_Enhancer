import logging

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from app.core.config import settings

logger = logging.getLogger(__name__)

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    future=True,
    echo=False,
    # Explicit pool sizing + liveness checks. pool_pre_ping runs a lightweight
    # check-out probe so a connection dropped by the DB/proxy during an idle
    # period is transparently replaced instead of surfacing as a 500;
    # pool_recycle retires connections before common idle timeouts. See the
    # db_pool_* settings for tuning (keep pool_size * workers < max_connections).
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_recycle=settings.db_pool_recycle,
    pool_pre_ping=settings.db_pool_pre_ping,
)
async_session = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def verify_database_startup() -> None:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            result = await conn.execute(
                text("SELECT extname FROM pg_extension WHERE extname = :ext"),
                {"ext": settings.pgvector_extension},
            )
            if result.scalar_one_or_none() is None:
                logger.warning(
                    f"pgvector extension '{settings.pgvector_extension}' is not installed. "
                    "Vector search endpoints will not work."
                )
            # Ensure tool_recommendations column exists in prompts table
            await conn.execute(text("ALTER TABLE prompts ADD COLUMN IF NOT EXISTS tool_recommendations JSONB;"))
            await conn.commit()
        logger.info("Database connection verified successfully and schema updated.")
    except Exception as e:
        logger.warning(
            f"Could not connect to database: {e}. "
            "The server will start but database-dependent endpoints will fail."
        )


async def ensure_vector_indexes() -> None:
    """Best-effort creation of the pgvector ANN indexes used by semantic search.

    A safety net mirroring the Alembic migration (same index names, so the two
    never conflict): it guarantees the HNSW indexes exist even in environments
    where ``alembic upgrade head`` hasn't been run yet. Without an index, every
    template/prompt similarity query is a full-table sequential scan plus
    per-row cosine math; the index turns that into an approximate-NN lookup.

    Idempotent (CREATE INDEX IF NOT EXISTS) and non-fatal — a failure here (for
    example pgvector < 0.5.0, which lacks HNSW) just logs and the app keeps
    working exactly as before via sequential scans.
    """
    statements = (
        "CREATE INDEX IF NOT EXISTS ix_templates_embedding_hnsw "
        "ON templates USING hnsw (embedding vector_cosine_ops);",
        "CREATE INDEX IF NOT EXISTS ix_prompts_embedding_hnsw "
        "ON prompts USING hnsw (embedding vector_cosine_ops);",
    )
    try:
        async with engine.begin() as conn:
            for stmt in statements:
                await conn.execute(text(stmt))
        logger.info("pgvector HNSW indexes ensured.")
    except Exception as e:
        logger.warning(
            "Could not ensure pgvector HNSW indexes: %s. Semantic search still "
            "works via sequential scan; run 'alembic upgrade head' (requires "
            "pgvector >= 0.5.0) to add them.",
            e,
        )
