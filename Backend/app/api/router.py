from fastapi import APIRouter

# Import sub-routers directly from the module routers
from app.modules.style_profiles.routers.analytics import router as analytics_router
from app.modules.style_profiles.routers.recommendation import router as recommendation_router
from app.modules.style_profiles.routers.delete import router as delete_router
from app.modules.style_profiles.routers.create import router as create_router
from app.modules.style_profiles.routers.import_export import router as import_export_router
from app.modules.style_profiles.routers.search import router as search_router
from app.modules.style_profiles.routers.activation import router as activation_router
from app.modules.style_profiles.routers.update import router as update_router
from app.modules.style_profiles.routers.read import router as read_router

api_router = APIRouter()

# Register sub-routers under "/v1" namespace.
# Note: order is critical because generic route parameters (e.g. GET /{id})
# must be registered after more specific paths (e.g. GET /deleted, GET /analytics)
# to avoid path collision/shadowing.
api_router.include_router(analytics_router, prefix="/v1")
api_router.include_router(recommendation_router, prefix="/v1")
api_router.include_router(delete_router, prefix="/v1")
api_router.include_router(create_router, prefix="/v1")
api_router.include_router(import_export_router, prefix="/v1")
api_router.include_router(search_router, prefix="/v1")
api_router.include_router(activation_router, prefix="/v1")
api_router.include_router(update_router, prefix="/v1")
api_router.include_router(read_router, prefix="/v1")
