import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import pytest
import pytest_asyncio
from typing import AsyncGenerator
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.session import get_async_session
from app.main import create_app

@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides a database session for testing, with automatic cleanup of created test records."""
    engine = create_async_engine(settings.database_url, future=True, echo=False)
    TestingSession = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with TestingSession() as session:
        yield session
        # Post-test cleanup of any test objects
        from sqlalchemy import delete
        from app.db.models import Template, Prompt, PromptVersion
        try:
            await session.execute(delete(PromptVersion).where(PromptVersion.change_summary.like("%TEST%") | PromptVersion.change_summary.like("%test%")))
            await session.execute(delete(Prompt).where(Prompt.title.like("%Test%") | Prompt.title.like("INTEL_%")))
            await session.execute(delete(Template).where(Template.title.like("%Test%")))
            await session.commit()
        except Exception:
            await session.rollback()
    await engine.dispose()

@pytest_asyncio.fixture(scope="function")
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Test client with override dependencies for session mapping."""
    app = create_app()

    engine = create_async_engine(settings.database_url, future=True, echo=False)
    TestingSession = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_async_session():
        async with TestingSession() as session:
            yield session

    app.dependency_overrides[get_async_session] = override_get_async_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()
    await engine.dispose()

@pytest.fixture(scope="function", autouse=True)
def mock_embedding_service_global(monkeypatch):
    """Mocks all EmbeddingService vector generations globally for test speed."""
    import math
    mock_vector = [1.0 / math.sqrt(384)] * 384
    
    monkeypatch.setattr(
        "app.services.embedding_service.EmbeddingService.generate_for_prompt",
        lambda self, prompt: mock_vector
    )
    monkeypatch.setattr(
        "app.services.embedding_service.EmbeddingService.generate",
        lambda self, texts: [mock_vector] * len(texts)
    )

@pytest.fixture(scope="function", autouse=True)
def mock_mistral_provider_global(monkeypatch):
    """Mocks all MistralProvider API endpoints globally for testing."""
    class MockResult:
        def __init__(self, enhanced_prompt="", score=None, grade=None, weaknesses=None, improvements=None, optimized_prompt=None):
            self.enhanced_prompt = enhanced_prompt or optimized_prompt or ""
            self.optimized_prompt = optimized_prompt or enhanced_prompt or ""
            self.score = score
            self.grade = grade
            self.weaknesses = weaknesses or []
            self.improvements = improvements or []
            self.text = self.optimized_prompt or "Mocked generation result"
            self.metadata = {"provider": "mistral"}

    class MockCheck:
        healthy = True

    # Bypass api_key check in __init__
    monkeypatch.setattr(
        "app.services.llm.mistral_provider.MistralProvider.__init__",
        lambda self: None
    )

    async def mock_optimize(self, prompt, template_id, **kwargs):
        return MockResult(
            optimized_prompt=f"Enhanced: {prompt} using template {template_id}",
            score=8.5,
            grade="A",
            weaknesses=["Original was vague"],
            improvements=["Structured", "Clear context"]
        )

    async def mock_analyze(self, prompt, **kwargs):
        return MockResult(
            enhanced_prompt="",
            score=4.2,
            grade="C",
            weaknesses=["Needs specific steps"],
            improvements=[]
        )

    async def mock_generate(self, prompt, **kwargs):
        print(f"\nDEBUG mock_generate prompt: {repr(prompt)}")
        import json
        if "Analyze the following user prompt" in prompt:
            analysis_data = {
                "summary": "The prompt is reasonably clear but lacks explicit constraints and examples.",
                "dimensions": {
                    "clarity": {
                        "score": 90,
                        "explanation": "Objective is clear.",
                        "suggestions": ["Add details."]
                    },
                    "context": {
                        "score": 80,
                        "explanation": "Context is provided.",
                        "suggestions": ["Include role background."]
                    },
                    "role_definition": {
                        "score": 65,
                        "explanation": "No explicit role defined.",
                        "suggestions": ["Define role."]
                    },
                    "output_format": {
                        "score": 70,
                        "explanation": "Format not specified.",
                        "suggestions": ["Define layout."]
                    },
                    "constraints": {
                        "score": 60,
                        "explanation": "Missing word limits.",
                        "suggestions": ["Add limits."]
                    },
                    "examples": {
                        "score": 40,
                        "explanation": "No examples.",
                        "suggestions": ["Provide few-shot examples."]
                    }
                }
            }
            res_str = json.dumps(analysis_data)
        elif "Compare the following Original Prompt" in prompt:
            comparison_data = {
                "differences": "Added context and formatting",
                "improvements": ["Clear structure"],
                "missing_issues_fixed": ["Vague target resolved"],
                "quality_delta": 2.5,
                "readability_improvement": "Better formatting",
                "summary": {
                    "before_score": 4.0,
                    "after_score": 8.5,
                    "score_improvement": 4.5,
                    "grade_improvement": "C to A",
                    "estimated_quality_increase_pct": 112.5,
                    "confidence": 0.95
                }
            }
            res_str = json.dumps(comparison_data)
        elif "inferred_role" in prompt or "JSON object" in prompt:
            res_str = '{"inferred_role": "Marketer", "inferred_mode": "Market Research"}'
        else:
            res_str = "Mocked generation result"

        return MockResult(
            enhanced_prompt="",
            score=None,
            grade=None,
            weaknesses=[],
            improvements=[],
            optimized_prompt=res_str
        )

    async def mock_health(self):
        return MockCheck()

    monkeypatch.setattr("app.services.llm.mistral_provider.MistralProvider.optimize_prompt", mock_optimize)
    monkeypatch.setattr("app.services.llm.mistral_provider.MistralProvider.analyze_prompt", mock_analyze)
    monkeypatch.setattr("app.services.llm.mistral_provider.MistralProvider.generate", mock_generate)
    monkeypatch.setattr("app.services.llm.mistral_provider.MistralProvider.health_check", mock_health)
