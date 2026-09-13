import asyncio
from app.db.session import async_session
from app.db.models import PromptVersion
from sqlalchemy import select
import re

def strip_variables_section(text: str) -> str:
    if not text:
        return ''

    pattern = re.compile(
        r'(?:(?:\r?\n){1,2}|^)[ \t]*(?:#{1,6}\s*|\*{1,2})?VARIABLES(?:\s+TO\s+FILL)?(?:\s*\([^)]*\))?:?(?:\*{1,2})?[ \t]*(?:\r?\n)(?:[ \t]*(?:[-*•]|\d+\.|{{|\[|`|\w+:).*(?:\r?\n|$)|[ \t]*(?:\r?\n|$))*(?=[ \t]*(?:#{1,6}\s+|[A-Z0-9 _-]{3,}:|\*{1,2}[A-Z0-9 _-]+:\*{1,2}|$))',
        re.IGNORECASE
    )

    cleaned = pattern.sub('\n', text)
    return cleaned.strip()

async def main():
    async with async_session() as session:
        vers = (await session.execute(select(PromptVersion))).scalars().all()
        found = 0
        for v in vers:
            if not v.content:
                continue
            if re.search(r'VARIABLES(?:\s+TO\s+FILL)?(?:\s*\([^)]*\))?:?', v.content, re.IGNORECASE):
                cleaned = strip_variables_section(v.content)
                if cleaned != v.content:
                    found += 1
                    print(f"=== Cleaned Prompt {v.prompt_id} v{v.version_number} ===")
                    # Check if VARIABLES is still in cleaned
                    if re.search(r'VARIABLES(?:\s+TO\s+FILL)?(?:\s*\([^)]*\))?:?', cleaned, re.IGNORECASE):
                        print("WARNING: VARIABLES STILL IN CLEANED!")
                    else:
                        print("SUCCESS: VARIABLES COMPLETELY REMOVED!")
        print(f"Total stripped: {found}")

if __name__ == "__main__":
    asyncio.run(main())
