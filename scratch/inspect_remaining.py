import asyncio
from app.db.session import async_session
from app.db.models import PromptVersion
from sqlalchemy import select
from uuid import UUID

async def main():
    async with async_session() as session:
        for pid in [UUID('d63da6f8-d1cc-4bd2-8f0e-599013e17f8b'), UUID('8d9041c6-ca25-474c-9bd5-fa43d1fc0bcd')]:
            v = (await session.execute(select(PromptVersion).where(PromptVersion.prompt_id == pid, PromptVersion.version_number == 2))).scalar_one()
            for line in v.content.split('\n'):
                if 'VARIABLE' in line.upper():
                    print(pid, '-->', line)

if __name__ == "__main__":
    asyncio.run(main())
