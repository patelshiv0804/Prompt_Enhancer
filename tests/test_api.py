import pytest
from sqlmodel import select
from app.db.models import AIModel, Profile, Template, Prompt, PromptVersion, StyleProfile

@pytest.mark.asyncio
async def test_health_endpoints(client):
    # Root Health Check
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"
    assert res.json()["database"] == "connected"

    # API v1 Health Check
    res = await client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    # Liveness Check
    res = await client.get("/api/v1/health/liveness")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"

    # Readiness Check
    res = await client.get("/api/v1/health/readiness")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"

    # Startup Check
    res = await client.get("/api/v1/health/startup")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_templates_api(client, db_session):
    # Retrieve AIModel
    model = (await db_session.execute(select(AIModel).limit(1))).scalars().first()
    
    # Insert templates
    t = Template(
        title="API Test Template",
        body="Translate: {prompt}",
        mode="api_test_mode",
        category="testing",
        ai_model_id=model.id,
        embedding=[0.01] * 384,
        is_approved=True
    )
    db_session.add(t)
    await db_session.commit()

    # List templates
    res = await client.get("/api/v1/templates/")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1

    # Filter templates by mode
    res = await client.get("/api/v1/templates/?mode=api_test_mode")
    assert res.status_code == 200
    assert len(res.json()["data"]) >= 1


@pytest.mark.asyncio
async def test_enhance_endpoint_workflow(client, db_session):
    model = (await db_session.execute(select(AIModel).limit(1))).scalars().first()
    profile = (await db_session.execute(select(Profile).limit(1))).scalars().first()
    
    tmpl = Template(
        title="Enhance Template",
        body="Optimize: {prompt}",
        mode="api_test_enhance",
        role="Marketer",
        ai_model_id=model.id,
        embedding=[0.02] * 384,
        is_approved=True
    )
    db_session.add(tmpl)
    await db_session.commit()

    headers = {"X-Current-User": profile.email}
    payload = {
        "role": "Marketer",
        "prompt": "Evaluate math equations.",
        "mode": "api_test_enhance",
    }
    
    res = await client.post("/api/v1/enhance", headers=headers, json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "Enhanced:" in data["data"]["enhanced_prompt"]
    assert data["data"]["template"]["title"] == "Enhance Template"


@pytest.mark.asyncio
async def test_prompts_crud_endpoints(client, db_session):
    model = (await db_session.execute(select(AIModel).limit(1))).scalars().first()
    profile = (await db_session.execute(select(Profile).limit(1))).scalars().first()

    prompt = Prompt(
        title="CRUD Test Prompt",
        original_prompt="Solve linear programming.",
        user_id=profile.id,
        ai_model_id=model.id,
        embedding=[0.03] * 384,
    )
    db_session.add(prompt)
    await db_session.commit()

    headers = {"X-Current-User": profile.email}

    # 1. Get Details
    res = await client.get(f"/api/v1/prompts/{prompt.id}", headers=headers)
    assert res.status_code == 200
    assert res.json()["data"]["original_prompt"] == "Solve linear programming."

    # 2. List with pagination filters
    res = await client.get("/api/v1/prompts/?page=1&page_size=5", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["data"]) >= 1

    # 3. Soft Delete
    res = await client.delete(f"/api/v1/prompts/{prompt.id}", headers=headers)
    assert res.status_code == 200
    assert res.json()["success"] is True

    # 4. Confirm soft-delete hides prompt
    res = await client.get(f"/api/v1/prompts/{prompt.id}", headers=headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_prompt_versions_restore(client, db_session):
    model = (await db_session.execute(select(AIModel).limit(1))).scalars().first()
    profile = (await db_session.execute(select(Profile).limit(1))).scalars().first()

    prompt = Prompt(
        title="Version Test Prompt",
        original_prompt="Version test raw",
        user_id=profile.id,
        ai_model_id=model.id,
        embedding=[0.04] * 384,
    )
    db_session.add(prompt)
    await db_session.flush()

    v1 = PromptVersion(prompt_id=prompt.id, version_number=1, version_type="initial", content="v1 content", change_summary="t")
    v2 = PromptVersion(prompt_id=prompt.id, version_number=2, version_type="enhancement", content="v2 content", change_summary="t")
    db_session.add(v1)
    db_session.add(v2)
    await db_session.flush()

    prompt.current_version_id = v2.id
    db_session.add(prompt)
    await db_session.commit()

    headers = {"X-Current-User": profile.email}

    # 1. List Versions
    res = await client.get(f"/api/v1/prompts/{prompt.id}/versions", headers=headers)
    assert res.status_code == 200
    assert len(res.json()["data"]) == 2

    # 2. Restore version 1
    res = await client.post(f"/api/v1/prompts/{prompt.id}/restore/1", headers=headers)
    assert res.status_code == 200
    assert res.json()["success"] is True

    # 3. Verify restore conflict (already active)
    res = await client.post(f"/api/v1/prompts/{prompt.id}/restore/1", headers=headers)
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_enhance_prompt_with_style_profile_api(client, db_session):
    import math
    mock_vector = [1.0 / math.sqrt(384)] * 384

    # Retrieve first profile and model
    profile = (await db_session.execute(select(Profile).limit(1))).scalars().first()
    model = (await db_session.execute(select(AIModel).limit(1))).scalars().first()
    assert model is not None

    # Create dummy template with matching embedding
    tmpl = Template(
        title="Regen API Test Template",
        body="Regen: {prompt}",
        mode="regen_api_mode",
        role="regen_api_role",
        ai_model_id=model.id,
        embedding=mock_vector,
        is_approved=True
    )
    db_session.add(tmpl)

    # Create style profile
    style = StyleProfile(
        name="API Style Profile Test",
        type="brand_voice",
        attributes={"tone": "cinematic", "mood": "dark"},
        is_active=True
    )
    db_session.add(style)
    await db_session.commit()

    try:
        headers = {"X-Current-User": profile.email}
        payload = {
            "role": "regen_api_role",
            "mode": "regen_api_mode",
            "prompt": "SaaS positioning pitch.",
            "apply_style": True,
            "style_profile_id": str(style.id),
        }
        res = await client.post("/api/v1/enhance", json=payload, headers=headers)
        assert res.status_code == 200
        assert res.json()["success"] is True
        assert "enhanced_prompt" in res.json()["data"]
    finally:
        await db_session.delete(style)
        await db_session.delete(tmpl)
        await db_session.commit()
