"""FastAPI entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import get_settings
from app.logging import configure_logging, get_logger
from app.routers import (
    auth,
    datasets,
    health,
    institution_admin,
    invites,
    platform_admin,
    storage,
    teacher,
)

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    logger.info(
        "api_starting",
        environment=settings.environment,
        version=__version__,
    )
    yield
    logger.info("api_stopping")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="DataBuddy API",
        version=__version__,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Mounted at /api so Next.js can reverse-proxy same-origin /api/*
    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(datasets.router, prefix="/api")
    app.include_router(teacher.router, prefix="/api")
    app.include_router(invites.router, prefix="/api")
    app.include_router(storage.router, prefix="/api")
    app.include_router(platform_admin.router, prefix="/api")
    app.include_router(institution_admin.router, prefix="/api")
    return app


app = create_app()
