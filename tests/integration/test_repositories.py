"""Integration tests for repository behavior shared by the API routes."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.db.models import UserSettings
from app.repositories.ai_model import AIModelRepository
from app.repositories.authRepository import AuthRepository
from app.repositories.profile import ProfileRepository
from app.repositories.prompt import PromptRepository
from app.repositories.prompt_version import PromptVersionRepository
from app.repositories.style_profiles import StyleProfileRepository
from app.repositories.template import TemplateRepository
from app.repositories.user import SettingsRepository
from app.schemas.style_profiles import CreateStyleProfileRequest, UpdateStyleProfileRequest
from tests import factories
from tests.stubs.embedding import hashed_embedding

pytestmark = pytest.mark.integration


async def test_base_repository_create_update_delete_and_exists_round_trip(
    db_session: AsyncSession,
) -> None:
    repo = AIModelRepository()
    model = factories.make_ai_model(provider="repo-round-trip")

    created = await repo.create(db_session, model)
    assert await repo.exists(db_session, str(created.id))

    updated = await repo.update(db_session, created, {"description": "Updated"})
    assert updated.description == "Updated"

    await repo.delete(db_session, updated)
    assert not await repo.exists(db_session, str(created.id))


async def test_ai_model_repository_finds_by_provider_and_active_flag(
    db_session: AsyncSession,
) -> None:
    repo = AIModelRepository()
    active = await factories.create_ai_model(db_session, provider="active-provider", is_active=True)
    inactive = await factories.create_ai_model(db_session, provider="inactive-provider", is_active=False)
    await db_session.commit()

    assert await repo.get_by_provider(db_session, "active-provider") == active
    active_models = await repo.list_active_models(db_session)
    assert active.id in [model.id for model in active_models]
    assert inactive.id not in [model.id for model in active_models]

    await repo.activate(db_session, inactive)
    assert inactive.id in [model.id for model in await repo.list_active_models(db_session)]


async def test_template_repository_filters_and_only_active_models(
    db_session: AsyncSession,
) -> None:
    repo = TemplateRepository()
    active_model = await factories.create_ai_model(db_session, is_active=True)
    inactive_model = await factories.create_ai_model(db_session, is_active=False)
    wanted = await factories.create_template(
        db_session,
        ai_model=active_model,
        role="Writer",
        mode="concise",
        category="marketing",
        is_featured=True,
        is_approved=True,
    )
    hidden = await factories.create_template(
        db_session,
        ai_model=inactive_model,
        role="Writer",
        mode="concise",
        category="marketing",
        is_featured=True,
        is_approved=True,
    )
    await db_session.commit()

    results = await repo.list_templates(
        db_session,
        role="writer",
        mode="concise",
        category="marketing",
        is_featured=True,
        is_approved=True,
        only_active_models=True,
    )

    ids = [template.id for template in results]
    assert wanted.id in ids
    assert hidden.id not in ids


async def test_template_vector_search_returns_similarity_order(
    db_session: AsyncSession,
) -> None:
    repo = TemplateRepository()
    near = await factories.create_template(
        db_session,
        body="postgres indexing query tuning",
        role="developer",
        mode="technical",
    )
    far = await factories.create_template(
        db_session,
        body="watercolor wedding invitation wording",
        role="writer",
        mode="creative",
    )
    await db_session.commit()

    results = await repo.search_templates_with_vector(
        db_session,
        hashed_embedding("postgres indexing query tuning"),
        is_approved=True,
        limit=2,
    )

    assert results[0][0].id == near.id
    assert results[0][1] > results[-1][1]
    assert far.id in [template.id for template, _score in results]


async def test_prompt_repository_filters_soft_delete_and_counts_user_rows(
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    repo = PromptRepository()
    template = await factories.create_template(db_session)
    visible = await factories.create_prompt(
        db_session,
        account=account,
        template_id=template.id,
        title="Visible",
    )
    await factories.create_prompt(
        db_session,
        account=account,
        template_id=template.id,
        deleted_at=datetime.now(timezone.utc),
    )
    stranger = await factories.create_account(db_session)
    await factories.create_prompt(db_session, account=stranger, template_id=template.id)
    await db_session.commit()

    prompts = await repo.list_prompts(
        db_session,
        user_id=str(account.id),
        template_id=str(template.id),
    )

    assert [prompt.id for prompt in prompts] == [visible.id]
    assert await repo.count_prompts(db_session, user_id=str(account.id)) == 1


async def test_prompt_repository_vector_search_can_scope_by_user_and_template(
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    repo = PromptRepository()
    template = await factories.create_template(db_session, role="developer", mode="coding")
    mine = await factories.create_prompt(
        db_session,
        account=account,
        template_id=template.id,
        original_prompt="debug a postgres query",
    )
    stranger = await factories.create_account(db_session)
    theirs = await factories.create_prompt(
        db_session,
        account=stranger,
        template_id=template.id,
        original_prompt="debug a postgres query",
    )
    await db_session.commit()

    results = await repo.search_prompts_with_vector(
        db_session,
        hashed_embedding("debug a postgres query"),
        user_id=str(account.id),
        template_id=str(template.id),
        role="developer",
        mode="coding",
    )

    ids = [prompt.id for prompt, _score in results]
    assert mine.id in ids
    assert theirs.id not in ids


async def test_prompt_version_repository_orders_and_counts_versions(
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    repo = PromptVersionRepository()
    prompt = await factories.create_prompt(db_session, account=account)
    second = await factories.create_prompt_version(db_session, prompt=prompt, version_number=2, content="second")
    first = await factories.create_prompt_version(db_session, prompt=prompt, version_number=1, content="first", set_current=False)
    await db_session.commit()

    versions = await repo.get_versions_by_prompt(db_session, str(prompt.id))

    assert [version.id for version in versions] == [first.id, second.id]
    assert await repo.count_versions(db_session, str(prompt.id)) == 2
    assert (await repo.get_latest_version(db_session, str(prompt.id))).id == second.id


async def test_profile_repository_finds_deactivates_and_filters_profiles(
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    repo = ProfileRepository()
    await db_session.commit()

    assert (await repo.get_by_email(db_session, account.email)).id == account.id
    await repo.deactivate(db_session, account.profile)

    active_ids = [profile.id for profile in await repo.list_profiles(db_session, is_active=True)]
    inactive_ids = [profile.id for profile in await repo.list_profiles(db_session, is_active=False)]
    assert account.id not in active_ids
    assert account.id in inactive_ids


async def test_auth_repository_crud_helpers(
    db_session: AsyncSession,
) -> None:
    repo = AuthRepository(db_session)
    email = factories.unique_email("auth-repo")
    hashed = hash_password("Secret123!")

    user = await repo.create(email=email, hashed_password=hashed, google_sub="google-1")

    assert await repo.exists_by_email(email)
    assert await repo.get_by_email(email) == user
    assert await repo.get_by_google_sub("google-1") == user
    await repo.update_verified(user.id, True)
    await repo.update_google_identity(user.id, google_sub="google-2", auth_provider="google")
    await repo.update_password(user.id, hash_password("NewSecret123!"))

    refreshed = await repo.get_by_id(user.id)
    assert refreshed.is_verified is True
    assert refreshed.google_sub == "google-2"
    assert refreshed.auth_provider == "google"
    assert verify_password("NewSecret123!", refreshed.hashed_password)


async def test_settings_repository_creates_updates_and_resets(
    db_session: AsyncSession,
) -> None:
    account = await factories.create_account(db_session)
    await db_session.execute(
        UserSettings.__table__.delete().where(UserSettings.user_id == account.id)
    )
    repo = SettingsRepository(db_session)

    defaults = await repo.create_defaults(account.id)
    assert defaults.user_id == account.id

    updated = await repo.update(account.id, theme="dark", default_model="claude")
    assert updated.theme == "dark"
    assert updated.default_model == "claude"

    reset = await repo.reset_to_defaults(account.id)
    assert reset.theme == "system"
    assert reset.default_model == "chatgpt"


async def test_style_profile_repository_visibility_soft_delete_and_search(
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    shared = await StyleProfileRepository.create_style(
        db_session,
        CreateStyleProfileRequest(
            name="Shared Brand",
            type="brand_voice",
            attributes={"tone": "shared"},
        ),
        user_id=None,
    )
    mine = await StyleProfileRepository.create_style(
        db_session,
        CreateStyleProfileRequest(
            name="My Brand",
            type="brand_voice",
            attributes={"tone": "mine"},
        ),
        user_id=account.id,
    )
    stranger_id = uuid4()
    theirs = await StyleProfileRepository.create_style(
        db_session,
        CreateStyleProfileRequest(
            name="Their Brand",
            type="brand_voice",
            attributes={"tone": "private"},
        ),
        user_id=stranger_id,
    )

    visible = await StyleProfileRepository.get_all_styles(db_session, user_id=account.id)
    visible_ids = [style.id for style in visible]
    assert mine.id in visible_ids
    assert shared.id in visible_ids
    assert theirs.id not in visible_ids

    found = await StyleProfileRepository.search_styles(db_session, "brand", "brand_voice", user_id=account.id)
    assert mine.id in [style.id for style in found]
    assert theirs.id not in [style.id for style in found]

    await StyleProfileRepository.update_style(
        db_session,
        mine,
        UpdateStyleProfileRequest(name="My Updated Brand", is_active=True),
    )
    await StyleProfileRepository.increment_use_count(db_session, mine)
    usage = await StyleProfileRepository.get_usage_history(db_session, user_id=account.id)
    assert any(row["style_id"] == str(mine.id) and row["use_count"] == 1 for row in usage)

    await StyleProfileRepository.soft_delete_style(db_session, mine)
    assert await StyleProfileRepository.get_style_by_id(db_session, mine.id, user_id=account.id) is None
    assert mine.id in [style.id for style in await StyleProfileRepository.get_deleted_styles(db_session, user_id=account.id)]
