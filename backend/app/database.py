from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from alembic.config import Config
from sqlalchemy import Engine, create_engine, func, select, update
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import Settings
from app.models import DataVersionRecord, OfficialPlaceRecord

if TYPE_CHECKING:
    from app.repositories.public_data import PublicDataRepository

_ENGINES: dict[str, Engine] = {}


def engine_for(database_url: str) -> Engine:
    engine = _ENGINES.get(database_url)
    if engine is not None:
        return engine
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)
    _ENGINES[database_url] = engine
    return engine


@contextmanager
def session_scope(settings: Settings) -> Iterator[Session]:
    with Session(engine_for(settings.database_url)) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def run_migrations(settings: Settings) -> None:
    if not settings.auto_migrate:
        return
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    command.upgrade(config, "head")


def sync_public_data(
    repository: PublicDataRepository,
    settings: Settings,
) -> None:
    manifest = repository.manifest
    version = str(manifest.get("dataset_version") or manifest["raw_resource"]["sha256"])
    now = datetime.now(UTC)
    with session_scope(settings) as session:
        session.execute(update(DataVersionRecord).values(active=False))
        data_version = session.get(DataVersionRecord, version)
        if data_version is None:
            data_version = DataVersionRecord(
                version=version,
                source_sha256=str(manifest["raw_resource"]["sha256"]),
                generated_at=manifest.get("generated_at"),
                active=True,
                metadata_json=manifest,
                recorded_at=now,
            )
            session.add(data_version)
            session.flush()
        else:
            data_version.active = True
            data_version.metadata_json = manifest

        existing = session.scalar(
            select(func.count(OfficialPlaceRecord.id)).where(
                OfficialPlaceRecord.data_version == version
            )
        )
        expected = len(repository.places) + len(repository.facilities)
        if int(existing or 0) == expected:
            return
        session.query(OfficialPlaceRecord).filter(
            OfficialPlaceRecord.data_version == version
        ).delete()
        records: list[OfficialPlaceRecord] = []
        for place in repository.places:
            payload = place.model_dump(mode="json")
            records.append(
                OfficialPlaceRecord(
                    data_version=version,
                    external_id=place.id,
                    kind=place.type,
                    name=place.name,
                    floor=place.floor,
                    lon=place.lon,
                    lat=place.lat,
                    published=True,
                    payload=payload,
                )
            )
        for facility in repository.facilities:
            payload = facility.model_dump(mode="json")
            records.append(
                OfficialPlaceRecord(
                    data_version=version,
                    external_id=facility.id,
                    kind="facility",
                    name=facility.name,
                    floor=facility.floor,
                    lon=facility.lon,
                    lat=facility.lat,
                    published=facility.publication_status == "published",
                    payload=payload,
                )
            )
        session.add_all(records)


def dispose_engines() -> None:
    for engine in _ENGINES.values():
        engine.dispose()
    _ENGINES.clear()
