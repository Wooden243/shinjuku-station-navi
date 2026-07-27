from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.config import Settings
from app.core.errors import RouteNotFoundError
from app.repositories.public_data import PublicDataRepository
from app.schemas.api import (
    FeatureCollection,
    HealthResponse,
    Place,
    RouteRequest,
    RouteResponse,
)
from app.services.routing import calculate_route

router = APIRouter(prefix="/api")


def repository_from(request: Request) -> PublicDataRepository:
    repository = getattr(request.app.state, "repository", None)
    if repository is None:
        error = getattr(request.app.state, "data_error", "データを読み込めません")
        raise HTTPException(status_code=503, detail=error)
    return repository


def settings_from(request: Request) -> Settings:
    return request.app.state.settings


Repository = Annotated[PublicDataRepository, Depends(repository_from)]
AppSettings = Annotated[Settings, Depends(settings_from)]


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    repository: PublicDataRepository | None = getattr(
        request.app.state, "repository", None
    )
    if repository is None:
        return HealthResponse(
            status="degraded",
            data_loaded=False,
            error=getattr(request.app.state, "data_error", "データを読み込めません"),
        )
    manifest = repository.manifest
    return HealthResponse(
        status="ok",
        data_loaded=True,
        data_mode=manifest["data_mode"],
        node_count=repository.graph.number_of_nodes(),
        link_count=int(manifest["link_count"]),
        gate_count=sum(place.type == "gate" for place in repository.places),
        exit_count=sum(place.type == "exit" for place in repository.places),
        floors=repository.floors,
        source={
            "title": manifest.get("title"),
            "provider": manifest.get("provider"),
            "license": manifest.get("license"),
            "license_url": manifest.get("license_url"),
            "catalog_url": manifest.get("catalog_url"),
            "specification_revision": manifest.get("specification_revision"),
            "generated_at": manifest.get("generated_at"),
            "source_map_version": manifest.get("source_map_version"),
            "crs": manifest.get("crs"),
        },
        warnings=list(manifest.get("warnings", [])),
    )


@router.get("/gates", response_model=list[Place])
def gates(repository: Repository) -> list[Place]:
    return [place for place in repository.places if place.type == "gate"]


@router.get("/exits", response_model=list[Place])
def exits(repository: Repository) -> list[Place]:
    return [place for place in repository.places if place.type == "exit"]


@router.get("/network", response_model=FeatureCollection)
def network(
    repository: Repository,
    floor: str = Query(min_length=1, max_length=20),
) -> dict[str, Any]:
    if floor not in repository.floors:
        raise HTTPException(status_code=404, detail="指定した階層は存在しません。")
    return repository.network_for_floor(floor)


@router.get("/floor-map", response_model=FeatureCollection)
def floor_map(
    repository: Repository,
    floor: str = Query(min_length=1, max_length=20),
) -> dict[str, Any]:
    if floor not in repository.floors:
        raise HTTPException(status_code=404, detail="指定した階層は存在しません。")
    return repository.floor_map_for_floor(floor)


@router.post("/routes", response_model=RouteResponse)
def route(
    payload: RouteRequest,
    repository: Repository,
    settings: AppSettings,
) -> RouteResponse:
    places = repository.places_by_id
    start = places.get(payload.start_gate_id)
    destination = places.get(payload.destination_exit_id)
    if start is None or start.type != "gate":
        raise HTTPException(status_code=404, detail="出発改札が見つかりません。")
    if destination is None or destination.type != "exit":
        raise HTTPException(status_code=404, detail="目的出口が見つかりません。")
    try:
        return calculate_route(
            repository,
            settings,
            start,
            destination,
            avoid_stairs=payload.preferences.avoid_stairs,
        )
    except RouteNotFoundError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

