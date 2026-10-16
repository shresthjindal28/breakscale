from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.components import router as component_router
from app.api.v1.simulations import router as simulations_router
from app.api.v1.users import router as users_router
from app.api.v1.websocket import router as websocket_router
from app.api.v1.workspaces import router as workspace_router
from app.core.config import get_settings

settings = get_settings()

api_router = APIRouter(prefix=settings.API_V1_PREFIX)
api_router.include_router(component_router)
api_router.include_router(websocket_router)
api_router.include_router(simulations_router)


@api_router.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


api_router.include_router(workspace_router)

api_router.include_router(auth_router)
api_router.include_router(users_router)
