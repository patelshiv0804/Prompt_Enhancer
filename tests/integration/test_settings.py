"""Integration tests for ``/api/v1/settings``."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import DEFAULT_SETTINGS
from app.db.models import UserSettings
from tests import factories

pytestmark = pytest.mark.integration

SETTINGS = "/api/v1/settings"


async def test_get_settings_returns_the_existing_row(
    authed_client: AsyncClient,
    account: factories.Account,
) -> None:
    response = await authed_client.get(SETTINGS)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user_id"] == str(account.id)
    assert set(body) >= {
        "id",
        "user_id",
        "theme",
        "default_mode",
        "default_model",
        "show_diff_by_default",
        "auto_detect_intent",
        "created_at",
        "updated_at",
    }


async def test_get_settings_auto_creates_defaults_when_the_row_is_missing(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    await db_session.execute(
        delete(UserSettings).where(UserSettings.user_id == account.id)
    )
    await db_session.commit()

    response = await authed_client.get(SETTINGS)

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == str(account.id)
    assert body["theme"] == DEFAULT_SETTINGS["theme"]
    assert body["default_mode"] == DEFAULT_SETTINGS["default_mode"]
    assert body["default_model"] == DEFAULT_SETTINGS["default_model"]
    assert body["show_diff_by_default"] == DEFAULT_SETTINGS["show_diff_by_default"]
    assert body["auto_detect_intent"] == DEFAULT_SETTINGS["auto_detect_intent"]


async def test_bulk_update_changes_multiple_fields_at_once(
    authed_client: AsyncClient,
) -> None:
    response = await authed_client.patch(
        SETTINGS,
        json={
            "theme": "dark",
            "default_mode": "coding",
            "default_model": "claude",
            "show_diff_by_default": False,
            "auto_detect_intent": False,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["theme"] == "dark"
    assert body["default_mode"] == "coding"
    assert body["default_model"] == "claude"
    assert body["show_diff_by_default"] is False
    assert body["auto_detect_intent"] is False


async def test_bulk_update_creates_defaults_first_when_missing(
    authed_client: AsyncClient,
    db_session: AsyncSession,
    account: factories.Account,
) -> None:
    await db_session.execute(
        delete(UserSettings).where(UserSettings.user_id == account.id)
    )
    await db_session.commit()

    response = await authed_client.patch(
        SETTINGS,
        json={"theme": "light", "default_model": "gemini"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["theme"] == "light"
    assert body["default_model"] == "gemini"
    assert body["default_mode"] == DEFAULT_SETTINGS["default_mode"]


async def test_auto_detect_intent_string_is_silently_ignored(
    authed_client: AsyncClient,
    account: factories.Account,
) -> None:
    before = (await authed_client.get(SETTINGS)).json()["auto_detect_intent"]

    response = await authed_client.patch(
        SETTINGS,
        json={"auto_detect_intent": "false"},
    )

    assert response.status_code == 200
    assert response.json()["auto_detect_intent"] == before


async def test_updating_theme_uses_the_specialized_endpoint(
    authed_client: AsyncClient,
) -> None:
    response = await authed_client.patch(f"{SETTINGS}/theme", json={"theme": "system"})

    assert response.status_code == 200
    assert response.json()["theme"] == "system"


async def test_updating_default_model_uses_the_specialized_endpoint(
    authed_client: AsyncClient,
) -> None:
    response = await authed_client.patch(
        f"{SETTINGS}/default-model",
        json={"default_model": "grok"},
    )

    assert response.status_code == 200
    assert response.json()["default_model"] == "grok"


async def test_updating_default_mode_uses_the_specialized_endpoint(
    authed_client: AsyncClient,
) -> None:
    response = await authed_client.patch(
        f"{SETTINGS}/default-mode",
        json={"default_mode": "creative"},
    )

    assert response.status_code == 200
    assert response.json()["default_mode"] == "creative"


async def test_toggling_intent_detection_uses_the_boolean_endpoint(
    authed_client: AsyncClient,
) -> None:
    response = await authed_client.patch(
        f"{SETTINGS}/intent-detection",
        json={"enabled": False},
    )

    assert response.status_code == 200
    assert response.json()["auto_detect_intent"] is False


async def test_toggling_diff_view_uses_the_boolean_endpoint(
    authed_client: AsyncClient,
) -> None:
    response = await authed_client.patch(
        f"{SETTINGS}/diff-view",
        json={"enabled": False},
    )

    assert response.status_code == 200
    assert response.json()["show_diff_by_default"] is False


async def test_settings_routes_require_authentication(
    client: AsyncClient,
) -> None:
    endpoints = [
        ("get", SETTINGS, None),
        ("patch", SETTINGS, {}),
        ("patch", f"{SETTINGS}/theme", {"theme": "dark"}),
        ("patch", f"{SETTINGS}/default-model", {"default_model": "claude"}),
        ("patch", f"{SETTINGS}/default-mode", {"default_mode": "coding"}),
        ("patch", f"{SETTINGS}/intent-detection", {"enabled": True}),
        ("patch", f"{SETTINGS}/diff-view", {"enabled": True}),
    ]

    for method, url, body in endpoints:
        response = await client.request(method, url, json=body)
        assert response.status_code == 401, (method, url, response.text)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("yes", True),
        ("no", False),
        ("true", True),
        ("off", False),
        ("1", True),
        (0, False),
    ],
)
async def test_boolean_endpoints_coerce_pydantic_recognised_truthy_strings(
    authed_client: AsyncClient,
    value: object,
    expected: bool,
) -> None:
    """``enabled: bool`` runs in pydantic's lax mode, so strings are coerced.

    Worth pinning rather than assuming: a client sending ``"no"`` gets 200 and
    intent detection switched *off*, not a 422. That is standard pydantic v2
    behaviour for ``bool`` outside strict mode, but it is also observable API
    behaviour that a stricter schema would change.
    """
    response = await authed_client.patch(
        f"{SETTINGS}/intent-detection",
        json={"enabled": value},
    )

    assert response.status_code == 200, response.text
    assert response.json()["auto_detect_intent"] is expected


@pytest.mark.parametrize("value", ["banana", 5, 1.5, [], {}, None])
async def test_boolean_endpoints_reject_values_pydantic_cannot_coerce(
    authed_client: AsyncClient,
    value: object,
) -> None:
    """Anything outside pydantic's recognised bool vocabulary is a 422."""
    response = await authed_client.patch(
        f"{SETTINGS}/intent-detection",
        json={"enabled": value},
    )

    assert response.status_code == 422, (value, response.text)
