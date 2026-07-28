from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    project_root = Path(__file__).resolve().parents[2]
    os.environ["SHINJUKU_DATA_DIR"] = str(project_root / "data" / "processed")
    os.environ.pop("SHINJUKU_ALLOW_FIXTURE_DATA", None)
    os.environ["DATABASE_URL"] = f"sqlite:///{(tmp_path / 'test.sqlite3').as_posix()}"
    os.environ["SHINJUKU_ADMIN_KEY"] = "test-admin-key"
    os.environ["SHINJUKU_SESSION_SECRET"] = "test-session-secret-is-at-least-32-characters"
    os.environ["SHINJUKU_CLIENT_HASH_SALT"] = "test-client-hash-salt"
    os.environ["SHINJUKU_ENV"] = "development"
    os.environ["SHINJUKU_AUTH_MODE"] = "development-key"
    os.environ["SHINJUKU_AUTO_MIGRATE"] = "true"
    os.environ["SHINJUKU_RATE_LIMIT"] = "6"

    from app.database import dispose_engines
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
    dispose_engines()
