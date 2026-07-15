import pytest
from uuid import uuid4
from sqlmodel import select

from app.db.models import AIModel, Profile, Template, Prompt, PromptVersion
from app.repositories.template import TemplateRepository
from app.repositories.prompt import PromptRepository
from app.repositories.prompt_version import PromptVersionRepository

@pytest.mark.asyncio
async def test_template_repository_operations(db_session):
    # Retrieve dependencies
    model = (await db_session.execute(select(AIModel).limit(1))).scalars().first()
    assert model is not None, "Ensure database models are seeded before running tests"

    repo = TemplateRepository()

    # Create mock template
    tmpl = Template(
        title="Test Retrieve Template",
        body="Optimize this text: {prompt}",
        mode="test_mode",
        category="general",
        role="assistant",
        ai_model_id=model.id,
        embedding=[0.05] * 384,
        is_approved=True
    )
    db_session.add(tmpl)
    await db_session.flush()

    # Test list_templates
    templates = await repo.list_templates(db_session, mode="test_mode")
    assert len(templates) >= 1
    assert templates[0].title == "Test Retrieve Template"

    # Test get_template
    fetched = await repo.get_by_id(db_session, tmpl.id)
    assert fetched is not None
    assert fetched.body == tmpl.body

    # Test search_templates_with_vector
    matches = await repo.search_templates_with_vector(db_session, [0.05] * 384, mode="test_mode", limit=2)
    assert len(matches) >= 1
    assert matches[0][0].id == tmpl.id


@pytest.mark.asyncio
async def test_prompt_repository_operations(db_session):
    model = (await db_session.execute(select(AIModel).limit(1))).scalars().first()
    profile = (await db_session.execute(select(Profile).limit(1))).scalars().first()
    assert model is not None and profile is not None

    repo = PromptRepository()

    # Create mock prompt
    prompt = Prompt(
        title="Test Repository Prompt",
        original_prompt="Summarize my files.",
        user_id=profile.id,
        ai_model_id=model.id,
        embedding=[0.1] * 384,
    )
    db_session.add(prompt)
    await db_session.flush()

    # Test get_prompt
    fetched = await repo.get_by_id(db_session, prompt.id)
    assert fetched is not None
    assert fetched.original_prompt == "Summarize my files."

    # Test list_prompts
    prompts = await repo.list_prompts(db_session, user_id=str(profile.id))
    assert len(prompts) >= 1
    assert any(p.id == prompt.id for p in prompts)

    # Test search_prompts_with_vector
    matches = await repo.search_prompts_with_vector(db_session, [0.1] * 384, limit=10, user_id=profile.id)
    assert len(matches) >= 1
    assert any(m[0].id == prompt.id for m in matches)
