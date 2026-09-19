import asyncio
import numpy as np
from sqlalchemy import select
from app.db.session import async_session
from app.db.models import Template
from app.services.embedding_service import EmbeddingService
from app.repositories.template import TemplateRepository

async def test():
    embedding_service = EmbeddingService()
    test_prompts = [
        "Find the ideal customer for my SaaS",
        "Write python unit tests for my database service",
        "Help me study for my biology exam notes and flashcards",
        "Create a marketing campaign for a luxury fashion brand"
    ]
    
    async with async_session() as session:
        repo = TemplateRepository()
        for prompt in test_prompts:
            print(f"\n==========================================")
            print(f"PROMPT: {prompt}")
            print(f"==========================================")
            vector = await embedding_service.generate_for_prompt_async(prompt)
            print(f"Vector dim: {len(vector)}, norm: {np.linalg.norm(vector):.4f}")
            
            # 1. Search with vector across ALL approved templates (no role filter)
            candidates_all = await repo.search_templates_with_vector(
                session=session,
                vector=vector,
                is_approved=True,
                limit=5
            )
            print(f"\nTop 5 matches (NO role filter):")
            for t, score in candidates_all:
                print(f"  Score: {score:.4f} | Role: {t.role} | Mode: {t.mode} | Title: {t.title}")
                
            # 2. Check template embedding stored in DB
            if candidates_all:
                top_temp, top_score = candidates_all[0]
                stored_emb = top_temp.embedding
                if stored_emb is not None:
                    stored_norm = np.linalg.norm(stored_emb)
                    dot_product = np.dot(vector, stored_emb)
                    cos_sim = dot_product / (np.linalg.norm(vector) * stored_norm)
                    print(f"\nDebug Top Match '{top_temp.title}':")
                    print(f"  Stored emb dim: {len(stored_emb)}, norm: {stored_norm:.4f}")
                    print(f"  Direct cosine similarity (numpy): {cos_sim:.4f}")
                    print(f"  pgvector returned score (1 - dist): {top_score:.4f}")

if __name__ == "__main__":
    asyncio.run(test())
