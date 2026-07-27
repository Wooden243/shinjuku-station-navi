from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    cors_origins: tuple[str, ...]
    walking_speed_m_per_minute: float = 80.0
    snap_warning_meters: float = 15.0


def get_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[3]
    data_dir = Path(
        os.getenv("SHINJUKU_DATA_DIR", str(project_root / "data" / "processed"))
    )
    origins = tuple(
        value.strip()
        for value in os.getenv(
            "SHINJUKU_CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if value.strip()
    )
    return Settings(data_dir=data_dir, cors_origins=origins)

