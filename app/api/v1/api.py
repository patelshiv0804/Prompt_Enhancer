from fastapi import APIRouter

from app.api.v1.ai_models import router as ai_models_router
from app.api.v1.health import router as health_router
from app.api.v1.prompts import router as prompts_router
from app.api.v1.templates import router as templates_router
from app.api.v1.enhancement import router as enhancement_router
from app.api.v1.delete import router as delete_router
from app.api.v1.create import router as create_router
from app.api.v1.activation import router as activation_router
from app.api.v1.update import router as update_router
from app.api.v1.read import router as read_router
from app.api.v1.auth import router as auth_router
from app.api.v1.user import router as user_router
from app.api.v1.settings import router as settings_router


api_router = APIRouter()
api_router.include_router(health_router, prefix="", tags=["health"])
api_router.include_router(enhancement_router, prefix="")
api_router.include_router(ai_models_router, prefix="", tags=["ai_models"])
api_router.include_router(templates_router, prefix="", tags=["templates"])
api_router.include_router(prompts_router, prefix="", tags=["prompts"])
api_router.include_router(delete_router, prefix="")
api_router.include_router(create_router, prefix="")
api_router.include_router(activation_router, prefix="")
api_router.include_router(update_router, prefix="")
api_router.include_router(read_router, prefix="")
api_router.include_router(auth_router, prefix="", tags=["Authentication"])
api_router.include_router(user_router, prefix="", tags=["Profile Management"])
api_router.include_router(settings_router, prefix="", tags=["User Settings"])
