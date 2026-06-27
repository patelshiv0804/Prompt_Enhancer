from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AIModel
from app.repositories.ai_model import AIModelRepository
from app.schemas.ai_model import AIModelCreate, AIModelUpdate
from app.services.exceptions import PromptNotFoundError


class AIModelService:
    def __init__(self, repository: AIModelRepository) -> None:
        self.repository = repository

    async def create_model(self, session: AsyncSession, model_data: AIModelCreate) -> AIModel:
        model = AIModel(**model_data.model_dump(exclude_none=True))
        return await self.repository.create(session, model)

    async def get_model(self, session: AsyncSession, model_id: str) -> AIModel:
        model = await self.repository.get_by_id(session, model_id)
        if model is None:
            raise PromptNotFoundError("AI model not found.")
        return model

    async def list_models(
        self,
        session: AsyncSession,
        only_active: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AIModel]:
        if only_active:
            return await self.repository.list_active_models(session, limit=limit, offset=offset)
        return await self.repository.get_all(session, limit=limit, offset=offset)

    async def update_model(self, session: AsyncSession, model_id: str, values: dict) -> AIModel:
        model = await self.get_model(session, model_id)
        return await self.repository.update(session, model, values)

    async def deactivate_model(self, session: AsyncSession, model_id: str) -> AIModel:
        model = await self.get_model(session, model_id)
        return await self.repository.deactivate(session, model)
