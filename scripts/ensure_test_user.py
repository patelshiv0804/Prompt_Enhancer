"""
ensure_test_user.py — guarantee one account with known credentials.

The test database is normally built by cloning the dev database
(scripts/bootstrap_test_db.sh clone). That clone brings across real `users` rows,
but their bcrypt hashes are one-way: we cannot recover any plaintext, so no
cloned account can log in. Integration and E2E tests that must exercise the real
POST /api/v1/auth/login endpoint therefore need an account whose password we
chose ourselves.

Idempotent — safe to re-run. An existing account is updated rather than
duplicated, which also resets the password if it ever drifts.

Hashing goes through the application's own app.core.security.hash_password so
the bcrypt cost factor matches exactly what the login path expects.

Run against the TEST database only:
    docker exec -e DATABASE_URL=postgresql+asyncpg://postgres:admin@db:5432/prompt_enhancer_test \
      promptiq-web python scripts/ensure_test_user.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.models import Profile, User, UserSettings
from app.db.session import async_session, engine

# Kept in sync with tests/constants.py — both sides of the login tests read the
# same literals.
TEST_USER_EMAIL = "test@promptiq.test"
TEST_USER_PASSWORD = "TestPassword123!"
TEST_USER_FULL_NAME = "Automated Test User"
TEST_USER_DISPLAY_NAME = "Tester"


def _guard_not_dev_database() -> None:
    """Refuse to write into a database that isn't clearly a test database.

    This script mutates user rows, so pointing it at the dev (or worse,
    production) database would silently rewrite a real account's password.
    """
    url = settings.database_url
    db_name = url.rsplit("/", 1)[-1].split("?")[0]
    if not db_name.endswith("_test"):
        raise SystemExit(
            f"REFUSING: database '{db_name}' does not end in '_test'.\n"
            "Set DATABASE_URL to the test database before running this script."
        )


async def ensure_test_user(session: AsyncSession) -> User:
    hashed = hash_password(TEST_USER_PASSWORD)

    user = (
        await session.execute(select(User).where(User.email == TEST_USER_EMAIL))
    ).scalar_one_or_none()

    if user is None:
        user = User(
            email=TEST_USER_EMAIL,
            hashed_password=hashed,
            auth_provider="local",
            is_active=True,
            is_verified=True,
        )
        session.add(user)
        await session.flush()
        action = "created"
    else:
        user.hashed_password = hashed
        user.is_active = True
        user.is_verified = True
        action = "updated"

    # Profile shares the user's primary key (profiles.id is a FK to users.id).
    profile = (
        await session.execute(select(Profile).where(Profile.id == user.id))
    ).scalar_one_or_none()

    if profile is None:
        profile = Profile(
            id=user.id,
            email=TEST_USER_EMAIL,
            full_name=TEST_USER_FULL_NAME,
            display_name=TEST_USER_DISPLAY_NAME,
            is_active=True,
            plan="pro",
            role="creator",
            # Pre-completed so dashboard tests are not blocked by the
            # onboarding modal. A dedicated onboarding test flips this back
            # inside its own rolled-back transaction.
            onboarding_completed=True,
        )
        session.add(profile)
        await session.flush()
    else:
        profile.is_active = True
        profile.onboarding_completed = True
        profile.deleted_at = None

    user_settings = (
        await session.execute(
            select(UserSettings).where(UserSettings.user_id == profile.id)
        )
    ).scalar_one_or_none()

    if user_settings is None:
        session.add(UserSettings(user_id=profile.id))

    await session.commit()
    print(f"  {action}: {TEST_USER_EMAIL} (id={user.id})")
    print(f"  password: {TEST_USER_PASSWORD}")
    return user


async def main() -> None:
    _guard_not_dev_database()
    async with async_session() as session:
        try:
            await ensure_test_user(session)
        except Exception:
            await session.rollback()
            raise
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
