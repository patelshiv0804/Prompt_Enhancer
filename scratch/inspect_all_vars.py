import asyncio
from app.db.session import async_session
from app.db.models import PromptVersion
from sqlalchemy import select
import re

async def main():
    async with async_session() as session:
        vers = (await session.execute(select(PromptVersion))).scalars().all()
        for v in vers:
            if not v.content:
                continue
            # Search for variables header
            match = re.search(r'(#*\s*VARIABLES(?:\s+TO\s+FILL)?(?:\s*\([^)]*\))?:?.*)', v.content, re.IGNORECASE)
            if match:
                idx = match.start()
                print(f"=== Prompt {v.prompt_id} v{v.version_number} ===")
                print(f"From index {idx} to end ({len(v.content)}):")
                print(v.content[idx:])
                print("="*60)

if __name__ == "__main__":
    asyncio.run(main())
