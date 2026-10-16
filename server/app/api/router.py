from fastapi import APIRouter

from app.core.config import get_settings

from app.api.v1.workspaces import router as workspace_router


settings = get_settings()

api_router = APIRouter(prefix=settings.API_V1_PREFIX)


@api_router.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@api_router.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


api_router.include_router(workspace_router)