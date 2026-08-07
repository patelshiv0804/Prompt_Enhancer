import logging

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from app.core.config import settings

logger = logging.getLogger(__name__)

engine: AsyncEngine = create_async_engine(settings.database_url, future=True, echo=False)
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
