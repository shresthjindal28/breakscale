from fastapi import APIRouter

from app.core.config import get_settings

settings = get_settings()

api_router = APIRouter(prefix=settings.API_V1_PREFIX)


@api_router.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }