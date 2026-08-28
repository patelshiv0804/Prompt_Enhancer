import pytest
from httpx import AsyncClient
from tests import factories
pytestmark = pytest.mark.integration

async def test_x(authed_client: AsyncClient, db_session, account, monkeypatch) -> None:
    import app.api.v1.prompts as mod
    real = mod.map_service_error
    def spy(exc):
        print("MAPPED:", type(exc).__name__, repr(exc)[:900])
        return real(exc)
    monkeypatch.setattr(mod, "map_service_error", spy)
    t = await factories.create_template(db_session, title="Nested Template")
    m = await factories.create_ai_model(db_session, model_name="nested-model")
    p = await factories.create_prompt(db_session, account=account, template_id=t.id, ai_model_id=m.id)
    pid = str(p.id)
    await db_session.commit()
    r = await authed_client.get(f"/api/v1/prompts/{pid}")
    print("STATUS:", r.status_code, r.text[:300])
