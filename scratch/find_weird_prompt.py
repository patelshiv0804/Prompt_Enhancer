import asyncio
from app.db.session import async_session
from app.db.models import Prompt, PromptVersion
from sqlalchemy import select

async def main():
    async with async_session() as session:
        prompts = (await session.execute(select(Prompt))).scalars().all()
        for p in prompts:
            vers = (await session.execute(
                select(PromptVersion)
                .where(PromptVersion.prompt_id == p.id)
                .order_by(PromptVersion.version_number)
            )).scalars().all()
            for v in vers:
                if v.content and "edfgnnnisckmxkwmd" in v.content:
                    print(f"FOUND PROMPT ID: {p.id}")
                    print(f"  Title: {p.title}")
                    print(f"  Original prompt: {p.original_prompt}")
                    print(f"  Total versions: {len(vers)}")
                    for vi in vers:
                        print(f"    v{vi.version_number}: content[:80] = {vi.content[:80] if vi.content else 'None'} | change={vi.change_summary}")
                    break

if __name__ == "__main__":
    asyncio.run(main())
