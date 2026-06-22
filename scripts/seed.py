"""
Seed script — Populate the database with sample data for development.

Usage:
    python -m scripts.seed
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_engine, get_session_factory, Base
from app.modules.auth.models import User
from app.modules.users.models import Profile, UserSettings
from app.core.security import hash_password
from app.core.logger import logger


async def seed():
    """Create tables and seed with sample data."""
    engine = get_engine()
    session_factory = get_session_factory()

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Tables created successfully")

    async with session_factory() as db:
        # Check if data already exists
        from sqlalchemy import select
        result = await db.execute(select(User).limit(1))
        if result.scalar_one_or_none():
            logger.info("Database already seeded. Skipping.")
            return

        # Create sample user
        user = User(
            email="shiv@gmail.com",
            hashed_password=hash_password("Test1234!"),
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        await db.flush()

        # Create profile
        profile = Profile(
            id=user.id,
            email=user.email,
            display_name="Shiv Patel",
            plan="free",
        )
        db.add(profile)
        await db.flush()

        # Create settings
        settings = UserSettings(user_id=user.id)
        db.add(settings)

        await db.commit()
        logger.info(f"Seeded user: {user.email} (id: {user.id})")

    await engine.dispose()
    logger.info("Seeding complete!")


if __name__ == "__main__":
    asyncio.run(seed())
