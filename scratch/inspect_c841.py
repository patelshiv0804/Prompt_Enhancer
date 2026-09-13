import asyncio
from app.db.session import async_session
from app.db.models import Prompt, PromptVersion
from sqlalchemy import select
from uuid import UUID

async def main():
    async with async_session() as session:
        p = await session.get(Prompt, UUID('c84131b6-9bda-494c-9a73-5728161a2d8a'))
        print("Prompt id:", p.id)
        print("Title:", p.title)
        print("Original prompt in DB:", repr(p.original_prompt))
        print("Template id:", p.template_id)
        print("Target model:", p.target_model)
        print("Created at:", p.created_at)
        
        vers = (await session.execute(
            select(PromptVersion)
            .where(PromptVersion.prompt_id == p.id)
            .order_by(PromptVersion.version_number)
        )).scalars().all()
        for v in vers:
            print(f"\n--- Version {v.version_number} ---")
            print("Content full:\n", v.content)

if __name__ == "__main__":
    asyncio.run(main())
