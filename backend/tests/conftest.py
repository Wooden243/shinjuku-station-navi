from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client() -> TestClient:
    project_root = Path(__file__).resolve().parents[2]
    os.environ["SHINJUKU_DATA_DIR"] = str(project_root / "data" / "processed")
    os.environ.pop("SHINJUKU_ALLOW_FIXTURE_DATA", None)

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client

