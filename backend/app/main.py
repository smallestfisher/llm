from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.bootstrap import init_backend_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_backend_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="BOE Data Copilot API", lifespan=lifespan)
    app.include_router(router, prefix="/api")
    return app


app = create_app()
