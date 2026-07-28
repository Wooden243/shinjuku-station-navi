from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _as_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    cors_origins: tuple[str, ...]
    database_url: str = "sqlite:///./data/submissions.sqlite3"
    environment: str = "development"
    auth_mode: str = "development-key"
    admin_key: str | None = None
    session_secret: str | None = None
    auth_proxy_shared_secret: str | None = None
    auto_migrate: bool = True
    walking_speed_m_per_minute: float = 80.0
    snap_warning_meters: float = 15.0
    submission_rate_limit: int = 6
    submission_rate_window_minutes: int = 10
    client_hash_salt: str = "development-only-change-me"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


def get_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[3]
    data_dir = Path(
        os.getenv("SHINJUKU_DATA_DIR", str(project_root / "data" / "processed"))
    )
    database_default = f"sqlite:///{(project_root / 'data' / 'submissions.sqlite3').as_posix()}"
    origins = tuple(
        value.strip()
        for value in os.getenv(
            "SHINJUKU_CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if value.strip()
    )
    environment = os.getenv("SHINJUKU_ENV", "development").strip().lower()
    auth_mode = os.getenv(
        "SHINJUKU_AUTH_MODE",
        "oidc-proxy" if environment == "production" else "development-key",
    ).strip()
    return Settings(
        data_dir=data_dir,
        cors_origins=origins,
        database_url=os.getenv("DATABASE_URL", database_default),
        environment=environment,
        auth_mode=auth_mode,
        admin_key=os.getenv("SHINJUKU_ADMIN_KEY"),
        session_secret=os.getenv("SHINJUKU_SESSION_SECRET"),
        auth_proxy_shared_secret=os.getenv("SHINJUKU_AUTH_PROXY_SHARED_SECRET"),
        auto_migrate=_as_bool("SHINJUKU_AUTO_MIGRATE", default=True),
        submission_rate_limit=int(os.getenv("SHINJUKU_RATE_LIMIT", "6")),
        submission_rate_window_minutes=int(
            os.getenv("SHINJUKU_RATE_WINDOW_MINUTES", "10")
        ),
        client_hash_salt=os.getenv(
            "SHINJUKU_CLIENT_HASH_SALT", "development-only-change-me"
        ),
    )
