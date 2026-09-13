import asyncio
from app.db.session import async_session
from app.db.models import PromptVersion
from sqlalchemy import select

async def main():
    async with async_session() as session:
        vers = (await session.execute(select(PromptVersion))).scalars().all()
        for v in vers:
            if v.content and "VARIABLES" in v.content.upper():
                print(f"Found in Prompt {v.prompt_id} v{v.version_number}:")
                # find the line with VARIABLES
                lines = v.content.split("\n")
                for i, line in enumerate(lines):
                    if "VARIABLE" in line.upper():
                        print(f"  Line {i}: {line}")
                        for j in range(i, min(len(lines), i + 10)):
                            print(f"    {lines[j]}")
                        break

if __name__ == "__main__":
    asyncio.run(main())
