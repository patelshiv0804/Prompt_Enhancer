"""Integration tests for custom template creation, management, and scoping."""

from __future__ import annotations

from uuid import uuid4
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests import factories
from tests.conftest import token_for

pytestmark = pytest.mark.integration

TEMPLATES_URL = "/api/v1/templates/"


async def test_create_custom_template_unauthenticated_fails(
    client: AsyncClient,
) -> None:
    payload = {
        "title": "My Secret Coding Template",
        "description": "A custom coding template",
        "body": "Act as an expert engineer: {{PROMPT}}",
        "role": "developer",
        "mode": "coding",
    }
    response = await client.post(TEMPLATES_URL, json=payload)
    assert response.status_code == 401, response.text


async def test_create_custom_template_success(
    authed_client: AsyncClient,
    account: factories.Account,
    db_session: AsyncSession,
) -> None:
    # Ensure active AI model exists
    model = await factories.create_ai_model(db_session, is_active=True)
    await db_session.commit()

    payload = {
        "title": "Architect Planner",
        "description": "Designs scalable systems",
        "body": "Think like a systems architect: {{PROMPT}}",
        "role": "developer",
        "mode": "system_design",
        "tags": ["architecture", "backend"],
        "ai_model_id": str(model.id),
    }
    response = await authed_client.post(TEMPLATES_URL, json=payload)
    assert response.status_code == 201, response.text
    data = response.json()

    assert data["title"] == "Architect Planner"
    assert data["body"] == "Think like a systems architect: {{PROMPT}}"
    assert data["role"] == "developer"
    assert data["mode"] == "system_design"
    assert data["user_id"] == str(account.id)
    assert data["is_custom"] is True
    assert data["is_approved"] is True


async def test_get_custom_template_owner_sees_body(
    authed_client: AsyncClient,
    account: factories.Account,
    db_session: AsyncSession,
) -> None:
    model = await factories.create_ai_model(db_session, is_active=True)
    await db_session.commit()

    payload = {
        "title": "Private Strategy",
        "body": "Private Prompt Body: {{PROMPT}}",
        "role": "strategist",
        "mode": "planning",
        "ai_model_id": str(model.id),
    }
    create_res = await authed_client.post(TEMPLATES_URL, json=payload)
    assert create_res.status_code == 201
    template_id = create_res.json()["id"]

    # Owner GET by ID
    get_res = await authed_client.get(f"{TEMPLATES_URL}{template_id}")
    assert get_res.status_code == 200
    detail = get_res.json()
    assert detail["id"] == template_id
    assert detail["body"] == "Private Prompt Body: {{PROMPT}}"
    assert detail["is_custom"] is True


async def test_get_custom_template_other_user_gets_404(
    client: AsyncClient,
    authed_client: AsyncClient,
    account: factories.Account,
    db_session: AsyncSession,
) -> None:
    model = await factories.create_ai_model(db_session, is_active=True)
    other_account = await factories.create_account(db_session)
    await db_session.commit()

    payload = {
        "title": "Confidential Template",
        "body": "Confidential Body: {{PROMPT}}",
        "role": "executive",
        "mode": "confidential",
        "ai_model_id": str(model.id),
    }
    create_res = await authed_client.post(TEMPLATES_URL, json=payload)
    assert create_res.status_code == 201
    template_id = create_res.json()["id"]

    # Unauthenticated client gets 404
    anon_res = await client.get(f"{TEMPLATES_URL}{template_id}")
    assert anon_res.status_code == 404

    # Other authenticated user gets 404 (zero information leakage)
    other_token = token_for(other_account.id)
    other_res = await client.get(
        f"{TEMPLATES_URL}{template_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert other_res.status_code == 404


async def test_list_templates_mine_filter(
    client: AsyncClient,
    authed_client: AsyncClient,
    account: factories.Account,
    db_session: AsyncSession,
) -> None:
    model = await factories.create_ai_model(db_session, is_active=True)
    # Create a system template
    await factories.create_template(db_session, ai_model_id=model.id, title="Public System Template")
    await db_session.commit()

    # Create a custom template for account
    payload = {
        "title": "My Personal Template",
        "body": "Personal Recipe: {{PROMPT}}",
        "role": "writer",
        "mode": "creative",
        "ai_model_id": str(model.id),
    }
    create_res = await authed_client.post(TEMPLATES_URL, json=payload)
    assert create_res.status_code == 201

    # Unauthenticated request with mine=true must be rejected
    unauth_res = await client.get(f"{TEMPLATES_URL}?mine=true")
    assert unauth_res.status_code == 401

    # Authenticated list with mine=true returns only account's custom templates
    mine_res = await authed_client.get(f"{TEMPLATES_URL}?mine=true")
    assert mine_res.status_code == 200
    mine_data = mine_res.json()["data"]
    assert len(mine_data) >= 1
    for t in mine_data:
        assert t["user_id"] == str(account.id)
        assert t["is_custom"] is True


async def test_update_custom_template_by_owner(
    authed_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    model = await factories.create_ai_model(db_session, is_active=True)
    await db_session.commit()

    payload = {
        "title": "Draft Template",
        "body": "Draft body",
        "role": "editor",
        "mode": "editing",
        "ai_model_id": str(model.id),
    }
    create_res = await authed_client.post(TEMPLATES_URL, json=payload)
    template_id = create_res.json()["id"]

    patch_res = await authed_client.patch(
        f"{TEMPLATES_URL}{template_id}",
        json={"title": "Polished Template", "description": "Now polished"},
    )
    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["title"] == "Polished Template"
    assert data["description"] == "Now polished"


async def test_update_custom_template_by_other_user_fails(
    client: AsyncClient,
    authed_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    model = await factories.create_ai_model(db_session, is_active=True)
    other_account = await factories.create_account(db_session)
    await db_session.commit()

    create_res = await authed_client.post(
        TEMPLATES_URL,
        json={
            "title": "Owner Template",
            "body": "Body",
            "ai_model_id": str(model.id),
        },
    )
    template_id = create_res.json()["id"]

    other_token = token_for(other_account.id)
    patch_res = await client.patch(
        f"{TEMPLATES_URL}{template_id}",
        json={"title": "Malicious Hijack"},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert patch_res.status_code == 404


async def test_delete_custom_template_by_owner(
    authed_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    model = await factories.create_ai_model(db_session, is_active=True)
    await db_session.commit()

    create_res = await authed_client.post(
        TEMPLATES_URL,
        json={
            "title": "Temporary Template",
            "body": "To be deleted",
            "ai_model_id": str(model.id),
        },
    )
    template_id = create_res.json()["id"]

    delete_res = await authed_client.delete(f"{TEMPLATES_URL}{template_id}")
    assert delete_res.status_code == 200

    # Ensure it no longer exists
    get_res = await authed_client.get(f"{TEMPLATES_URL}{template_id}")
    assert get_res.status_code == 404


async def test_enhance_prompt_with_owned_custom_template(
    authed_client: AsyncClient,
    account: factories.Account,
    db_session: AsyncSession,
) -> None:
    model = await factories.create_ai_model(db_session, is_active=True)
    await db_session.commit()

    create_res = await authed_client.post(
        TEMPLATES_URL,
        json={
            "title": "Custom Architect",
            "body": "Role: Systems Architect.\n{{PROMPT}}",
            "role": "developer",
            "mode": "system_design",
            "ai_model_id": str(model.id),
        },
    )
    assert create_res.status_code == 201
    template_id = create_res.json()["id"]

    enhance_res = await authed_client.post(
        "/api/v1/enhance",
        json={
            "prompt": "Design a high-throughput cache layer.",
            "template_id": template_id,
        },
    )
    assert enhance_res.status_code == 200, enhance_res.text
    body = enhance_res.json()
    assert body["data"]["template"]["id"] == template_id


async def test_enhance_prompt_with_other_user_custom_template_fails(
    client: AsyncClient,
    authed_client: AsyncClient,
    account: factories.Account,
    db_session: AsyncSession,
) -> None:
    model = await factories.create_ai_model(db_session, is_active=True)
    other_account = await factories.create_account(db_session)
    await db_session.commit()

    # User 1 creates custom template
    create_res = await authed_client.post(
        TEMPLATES_URL,
        json={
            "title": "Private Architect",
            "body": "Secret body {{PROMPT}}",
            "role": "developer",
            "mode": "coding",
            "ai_model_id": str(model.id),
        },
    )
    template_id = create_res.json()["id"]

    # User 2 attempts to use User 1's private custom template ID
    other_token = token_for(other_account.id)
    enhance_res = await client.post(
        "/api/v1/enhance",
        json={
            "prompt": "Design a cache layer.",
            "template_id": template_id,
        },
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert enhance_res.status_code == 404

