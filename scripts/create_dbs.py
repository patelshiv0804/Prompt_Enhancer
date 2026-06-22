"""Create the prompt_enhancer and prompt_enhancer_test databases."""
import asyncio
import asyncpg


async def create_dbs():
    conn = await asyncpg.connect(
        user="postgres", password="admin", host="localhost", port=5432, database="postgres"
    )
    for db_name in ["prompt_enhancer", "prompt_enhancer_test"]:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname=$1", db_name
        )
        if not exists:
            await conn.execute(f"CREATE DATABASE {db_name}")
            print(f"Created database: {db_name}")
        else:
            print(f"Database already exists: {db_name}")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(create_dbs())
