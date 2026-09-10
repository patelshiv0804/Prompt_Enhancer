import asyncio
import os
import sys
from logging.config import fileConfig

# Add project root to sys.path so 'app' can be imported when running alembic from anywhere
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config, create_async_engine

from alembic import context

from app.core.config import settings
from sqlmodel import SQLModel
import app.db.models  # noqa: F401

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = SQLModel.metadata


def run_migrations_online() -> None:
    connectable = create_async_engine(settings.database_url, poolclass=pool.NullPool)

    def do_run_migrations(connection):
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()

    async def run_async_migrations() -> None:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
        await connectable.dispose()

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    raise RuntimeError("Alembic offline mode is not supported.")
else:
    run_migrations_online()

