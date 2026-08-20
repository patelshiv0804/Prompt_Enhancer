"""
recompute_template_embeddings.py
====================================
Recomputes and updates all template vectors in the database by generating
embeddings using ONLY metadata fields (Role, Mode, Category, Title, Description, Tags),
deliberately excluding the large `body` text to avoid token truncation and vector dilution.

Usage:
  python scripts/recompute_template_embeddings.py
"""

import asyncio
import os
import sys
from sqlalchemy import select

# Make sure `app` package is importable when run from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import async_session
from app.db.models import Template
from app.services.embedding_service import EmbeddingService


def build_template_embedding_text(template: Template) -> str:
    tags_str = ", ".join(template.tags) if template.tags else "None"
    return (
        f"Role:\n{template.role or 'N/A'}\n\n"
        f"Mode:\n{template.mode or 'N/A'}\n\n"
        f"Category:\n{template.category or 'N/A'}\n\n"
        f"Title:\n{template.title or 'N/A'}\n\n"
        f"Description:\n{template.description or 'N/A'}\n\n"
        f"Tags:\n{tags_str}"
    )


async def recompute_embeddings() -> None:
    print("\n🔄 Starting template embedding re-computation (excluding body)...\n")
    embedding_service = EmbeddingService()

    async with async_session() as session:
        result = await session.execute(select(Template))
        templates = result.scalars().all()

        if not templates:
            print("⚠️ No templates found in the database.")
            return

        print(f"  Found {len(templates)} templates to update.\n")

        for index, template in enumerate(templates, 1):
            text = build_template_embedding_text(template)
            new_embedding = embedding_service.generate_for_prompt(text)
            template.embedding = new_embedding
            print(f"  ✔ [{index}/{len(templates)}] Updated embedding for '{template.title}' (Role: {template.role}, Mode: {template.mode})")

        await session.commit()
        print("\n✅ All template embeddings re-computed and saved to database successfully!\n")


if __name__ == "__main__":
    asyncio.run(recompute_embeddings())
