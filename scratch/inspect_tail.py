import asyncio
from app.db.session import async_session
from app.db.models import PromptVersion
from sqlalchemy import select
from uuid import UUID

async def main():
    async with async_session() as session:
        v = (await session.execute(
            select(PromptVersion)
            .where(PromptVersion.prompt_id == UUID('b8f69fe5-bc4d-4b9b-8dc4-9a73aa0eefc5'))
            .where(PromptVersion.version_number == 3)
        )).scalar_one()
        print("=== Full tail of b8f69fe5 v3 ===")
        print(v.content[-600:])

if __name__ == "__main__":
    asyncio.run(main())
