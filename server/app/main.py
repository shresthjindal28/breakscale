from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError

from app.api.router import api_router
from app.core.config import get_settings
from app.infrastructure.body_limit import BodyLimitMiddleware

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"Starting {settings.APP_NAME}")
    yield
    print(f"Stopping {settings.APP_NAME}")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.trusted_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(BodyLimitMiddleware,max_bytes=settings.MAX_WS_MESSAGE_BYTES)

    @app.exception_handler(RedisError)
    async def redis_unavailable(request, exc):
        return JSONResponse({"detail":"Simulation service temporarily unavailable"},status_code=503)

    app.include_router(api_router)

    return app


app = create_app()