"""Unit tests for PromptVersionService, PromptRestoreService, and PromptRegenerationService.

Covers:
- Commit 157c2c2: core prompt enhancement, regeneration, and versioning service layer
- Commit b27692a: prompt version management and restoration service
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
import pytest

from app.db.models import Prompt, PromptVersion
from app.services.exceptions import (
    PromptNotFoundError,
    PromptVersionException,
    VersionNotFoundError,
)
from app.services.prompt_regeneration_service import PromptRegenerationService
from app.services.prompt_restore_service import PromptRestoreService
from app.services.prompt_version_service import PromptVersionService

pytestmark = pytest.mark.unit


# ─────────────────────────────────────────────────────────────────────────────
# PromptVersionService tests (commit 157c2c2)
# ─────────────────────────────────────────────────────────────────────────────


def test_clean_version_content_strips_markdown_formatting() -> None:
    """Removes bold, code backticks, and header markers from prompt version text."""
    dirty_text = "### Header\nThis is **bold** and `code` with _italic_."
    cleaned = PromptVersionService._clean_version_content(dirty_text)

    assert "###" not in cleaned
    assert "**" not in cleaned
    assert "`" not in cleaned
    assert "_" not in cleaned
    assert "Header\nThis is bold and code with italic." in cleaned


@pytest.mark.asyncio
async def test_create_version_first_version_is_one() -> None:
    """If no prior versions exist, the created version number starts at 1."""
    prompt_id = uuid4()
    mock_prompt = MagicMock(spec=Prompt)
    mock_prompt.id = prompt_id
    mock_prompt.current_version_id = None

    mock_prompt_repo = MagicMock()
    mock_prompt_repo.update = AsyncMock()

    mock_version_repo = MagicMock()
    mock_version_repo.get_latest_version = AsyncMock(return_value=None)
    mock_version_repo.create = AsyncMock(side_effect=lambda session, v: v)

    service = PromptVersionService(
        prompt_repository=mock_prompt_repo,
        prompt_version_repository=mock_version_repo,
    )

    mock_session = AsyncMock()
    version = await service.create_version(
        session=mock_session,
        prompt=mock_prompt,
        content="Optimized prompt text",
        version_type="INITIAL",
    )

    assert version.version_number == 1
    assert version.content == "Optimized prompt text"
    assert version.version_type == "INITIAL"
    assert mock_prompt.current_version_id == version.id


@pytest.mark.asyncio
async def test_create_version_increments_sequence() -> None:
    """Subsequent versions increment sequentially (N + 1)."""
    prompt_id = uuid4()
    mock_prompt = MagicMock(spec=Prompt)
    mock_prompt.id = prompt_id

    prior_version = MagicMock(spec=PromptVersion)
    prior_version.version_number = 3

    mock_prompt_repo = MagicMock()
    mock_prompt_repo.update = AsyncMock()

    mock_version_repo = MagicMock()
    mock_version_repo.get_latest_version = AsyncMock(return_value=prior_version)
    mock_version_repo.create = AsyncMock(side_effect=lambda session, v: v)

    service = PromptVersionService(
        prompt_repository=mock_prompt_repo,
        prompt_version_repository=mock_version_repo,
    )

    mock_session = AsyncMock()
    version = await service.create_version(
        session=mock_session,
        prompt=mock_prompt,
        content="Second iteration",
        version_type="REGENERATION",
    )

    assert version.version_number == 4


@pytest.mark.asyncio
async def test_create_version_rejects_empty_content() -> None:
    """Raises PromptVersionException if content is empty or only whitespace."""
    service = PromptVersionService(
        prompt_repository=MagicMock(),
        prompt_version_repository=MagicMock(),
    )

    with pytest.raises(PromptVersionException) as exc_info:
        await service.create_version(
            session=AsyncMock(),
            prompt=MagicMock(spec=Prompt),
            content="   \n   ",
            version_type="INITIAL",
        )

    assert "cannot be empty" in str(exc_info.value)


# ─────────────────────────────────────────────────────────────────────────────
# PromptRestoreService tests (commit b27692a & 157c2c2)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_restore_version_successful() -> None:
    """Successfully points current_version_id to target version and updates embedding."""
    prompt_id = uuid4()
    version_id = uuid4()

    mock_prompt = MagicMock(spec=Prompt)
    mock_prompt.id = prompt_id
    mock_prompt.current_version_id = uuid4()  # different version currently

    mock_version = MagicMock(spec=PromptVersion)
    mock_version.id = version_id
    mock_version.prompt_id = prompt_id

    mock_prompt_repo = MagicMock()
    mock_prompt_repo.get_by_id = AsyncMock(return_value=mock_prompt)
    mock_prompt_repo.update = AsyncMock()

    mock_version_repo = MagicMock()
    mock_version_repo.get_by_id = AsyncMock(return_value=mock_version)

    mock_embedding_service = MagicMock()
    mock_embedding_service.update_prompt_embedding = AsyncMock()

    restore_service = PromptRestoreService(
        prompt_repository=mock_prompt_repo,
        prompt_version_repository=mock_version_repo,
        prompt_embedding_service=mock_embedding_service,
    )

    mock_session = AsyncMock()
    result = await restore_service.restore_version(
        session=mock_session,
        prompt_id=str(prompt_id),
        version_id=str(version_id),
    )

    assert result["prompt_id"] == str(prompt_id)
    assert result["restored_version_id"] == str(version_id)
    assert mock_prompt.current_version_id == version_id
    mock_embedding_service.update_prompt_embedding.assert_awaited_once_with(
        mock_session, str(prompt_id)
    )


@pytest.mark.asyncio
async def test_restore_version_idempotent_when_already_active() -> None:
    """If the target version is already current, returns early without writing updates."""
    prompt_id = uuid4()
    version_id = uuid4()

    mock_prompt = MagicMock(spec=Prompt)
    mock_prompt.id = prompt_id
    mock_prompt.current_version_id = version_id  # already active

    mock_version = MagicMock(spec=PromptVersion)
    mock_version.id = version_id
    mock_version.prompt_id = prompt_id

    mock_prompt_repo = MagicMock()
    mock_prompt_repo.get_by_id = AsyncMock(return_value=mock_prompt)
    mock_prompt_repo.update = AsyncMock()

    mock_version_repo = MagicMock()
    mock_version_repo.get_by_id = AsyncMock(return_value=mock_version)

    mock_embedding_service = MagicMock()
    mock_embedding_service.update_prompt_embedding = AsyncMock()

    restore_service = PromptRestoreService(
        prompt_repository=mock_prompt_repo,
        prompt_version_repository=mock_version_repo,
        prompt_embedding_service=mock_embedding_service,
    )

    mock_session = AsyncMock()
    result = await restore_service.restore_version(
        session=mock_session,
        prompt_id=str(prompt_id),
        version_id=str(version_id),
    )

    assert result["restored_version_id"] == str(version_id)
    mock_prompt_repo.update.assert_not_called()
    mock_embedding_service.update_prompt_embedding.assert_not_called()


@pytest.mark.asyncio
async def test_restore_version_raises_when_prompt_not_found() -> None:
    """Raises PromptNotFoundError when prompt does not exist."""
    mock_prompt_repo = MagicMock()
    mock_prompt_repo.get_by_id = AsyncMock(return_value=None)

    restore_service = PromptRestoreService(
        prompt_repository=mock_prompt_repo,
        prompt_version_repository=MagicMock(),
        prompt_embedding_service=MagicMock(),
    )

    with pytest.raises(PromptNotFoundError):
        await restore_service.restore_version(
            session=AsyncMock(),
            prompt_id=str(uuid4()),
            version_id=str(uuid4()),
        )


@pytest.mark.asyncio
async def test_restore_version_raises_when_version_belongs_to_different_prompt() -> None:
    """Raises VersionNotFoundError if version belongs to a different prompt."""
    prompt_id = uuid4()
    other_prompt_id = uuid4()

    mock_prompt = MagicMock(spec=Prompt)
    mock_prompt.id = prompt_id

    mock_version = MagicMock(spec=PromptVersion)
    mock_version.id = uuid4()
    mock_version.prompt_id = other_prompt_id  # mismatch

    mock_prompt_repo = MagicMock()
    mock_prompt_repo.get_by_id = AsyncMock(return_value=mock_prompt)

    mock_version_repo = MagicMock()
    mock_version_repo.get_by_id = AsyncMock(return_value=mock_version)

    restore_service = PromptRestoreService(
        prompt_repository=mock_prompt_repo,
        prompt_version_repository=mock_version_repo,
        prompt_embedding_service=MagicMock(),
    )

    with pytest.raises(VersionNotFoundError):
        await restore_service.restore_version(
            session=AsyncMock(),
            prompt_id=str(prompt_id),
            version_id=str(mock_version.id),
        )


# ─────────────────────────────────────────────────────────────────────────────
# PromptRegenerationService tests (commit 157c2c2)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_regenerate_prompt_raises_when_not_found() -> None:
    """Raises PromptNotFoundError if target prompt does not exist."""
    mock_prompt_repo = MagicMock()
    mock_prompt_repo.get_by_id = AsyncMock(return_value=None)

    service = PromptRegenerationService(
        prompt_repository=mock_prompt_repo,
        template_repository=MagicMock(),
        prompt_version_service=MagicMock(),
        prompt_embedding_service=MagicMock(),
        analysis_service=MagicMock(),
        llm_provider=MagicMock(),
        enhancement_service=MagicMock(),
    )

    with pytest.raises(PromptNotFoundError):
        await service.regenerate_prompt(
            session=AsyncMock(),
            prompt_id=str(uuid4()),
        )


@pytest.mark.asyncio
async def test_regenerate_prompt_raises_when_no_active_version() -> None:
    """Raises PromptVersionException if prompt has no active current_version_id."""
    mock_prompt = MagicMock(spec=Prompt)
    mock_prompt.current_version_id = None
    mock_prompt.deleted_at = None

    mock_prompt_repo = MagicMock()
    mock_prompt_repo.get_by_id = AsyncMock(return_value=mock_prompt)

    service = PromptRegenerationService(
        prompt_repository=mock_prompt_repo,
        template_repository=MagicMock(),
        prompt_version_service=MagicMock(),
        prompt_embedding_service=MagicMock(),
        analysis_service=MagicMock(),
        llm_provider=MagicMock(),
        enhancement_service=MagicMock(),
    )

    with pytest.raises(PromptVersionException) as exc_info:
        await service.regenerate_prompt(
            session=AsyncMock(),
            prompt_id=str(uuid4()),
        )

    assert "no active version" in str(exc_info.value)
