from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router
from app.core.config import get_settings
from app.core.errors import DataLoadError
from app.repositories.public_data import load_public_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.repository = None
    app.state.data_error = None
    try:
        app.state.repository = load_public_data(settings.data_dir)
    except DataLoadError as exc:
        app.state.data_error = str(exc)
    yield


settings = get_settings()
app = FastAPI(
    title="Shinjuku Open Nav API",
    version="1.0.0",
    description="東京都オープンデータを用いた新宿駅階層別歩行経路API",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(router)

