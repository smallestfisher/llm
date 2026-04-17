from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import env as _env  # noqa: F401
from app.api.routes import router
from app.bootstrap import init_backend_db
from app.logging_config import configure_logging


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_backend_db()
    yield


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="BOE Data Copilot API", lifespan=lifespan)
    app.include_router(router, prefix="/api")
    return app


app = create_app()
