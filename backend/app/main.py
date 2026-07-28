from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router
from app.core.config import get_settings
from app.core.errors import DataLoadError
from app.database import run_migrations, sync_public_data
from app.repositories.public_data import load_public_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.repository = None
    app.state.data_error = None
    app.state.database_ready = False
    app.state.database_error = None
    try:
        app.state.repository = load_public_data(settings.data_dir)
    except DataLoadError as exc:
        app.state.data_error = str(exc)
    try:
        run_migrations(settings)
        if app.state.repository is not None:
            sync_public_data(app.state.repository, settings)
        app.state.database_ready = True
    except Exception as exc:  # DB障害時も読み取り専用ナビゲーションは継続する。
        app.state.database_error = str(exc)
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
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=[
        "Content-Type",
        "X-Admin-Key",
        "X-Client-Id",
        "X-Authenticated-User",
        "X-Auth-Proxy-Secret",
    ],
)
app.include_router(router)
