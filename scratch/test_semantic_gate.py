import asyncio
from app.db.session import async_session
from app.repositories.template import TemplateRepository
from app.services.embedding_service import EmbeddingService
from app.core.config import settings

async def test_gate():
    repo = TemplateRepository()
    emb_service = EmbeddingService()

    print("==========================================")
    print(f"TESTING SEMANTIC GATE ROUTING (THRESHOLD = {settings.general_template_match_threshold})")
    print("==========================================")

    async with async_session() as session:
        # Test Case 1: Matching template (e.g. Email Marketing Campaign)
        query_match = "Create an email marketing campaign for a new SaaS product launch"
        print(f"\n[Test 1] Query: '{query_match}'")
        emb1 = await emb_service.generate_for_prompt_cached(query_match)
        candidates1 = await repo.search_templates_with_vector(
            session=session,
            vector=emb1,
            is_approved=True,
            limit=1,
        )
        if candidates1:
            top_t, top_s = candidates1[0]
            print(f"Top Candidate: '{top_t.title}' | Similarity: {top_s:.4f}")
            is_above = top_s >= settings.general_template_match_threshold
            print(f"Decision: {'[TEMPLATE ROUTE] Score >= ' + str(settings.general_template_match_threshold) if is_above else '[AMPE FALLBACK]'}")
            assert is_above, f"Test 1 failed: score {top_s:.4f} < {settings.general_template_match_threshold}"
        else:
            raise AssertionError("Test 1 returned no candidates")

        # Test Case 2: Broad/generic prompt with no specific template match
        query_generic = "Help me draft a friendly message to my neighbor asking them to keep the noise down tonight"
        print(f"\n[Test 2] Query: '{query_generic}'")
        emb2 = await emb_service.generate_for_prompt_cached(query_generic)
        candidates2 = await repo.search_templates_with_vector(
            session=session,
            vector=emb2,
            is_approved=True,
            limit=1,
        )
        if candidates2:
            top_t2, top_s2 = candidates2[0]
            print(f"Top Candidate: '{top_t2.title}' | Similarity: {top_s2:.4f}")
            is_above2 = top_s2 >= settings.general_template_match_threshold
            print(f"Decision: {'[TEMPLATE ROUTE]' if is_above2 else '[AMPE FALLBACK] Score < ' + str(settings.general_template_match_threshold)}")
            assert not is_above2, f"Test 2 failed: score {top_s2:.4f} >= {settings.general_template_match_threshold}"
        else:
            print("No candidates found -> AMPE fallback")

    print("\n✅ All semantic gate tests passed successfully!")

if __name__ == "__main__":
    asyncio.run(test_gate())
