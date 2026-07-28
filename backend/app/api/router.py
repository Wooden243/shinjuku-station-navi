from __future__ import annotations

import csv
import io
import json
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response

from app.core.auth import (
    clear_admin_session,
    create_development_session,
    verify_admin_request,
)
from app.core.config import Settings
from app.core.errors import RouteNotFoundError
from app.repositories.public_data import PublicDataRepository
from app.repositories.submissions import (
    SubmissionRateLimitError,
    create_submission,
    get_submission,
    hash_client_identifier,
    list_audit_logs,
    list_submissions,
    official_nearby,
    review_submission,
    similar_submissions,
)
from app.schemas.api import (
    AdminSessionCreate,
    AdminSessionResponse,
    AdminSubmissionDetail,
    AuditLog,
    DataSource,
    Facility,
    FeatureCollection,
    HealthResponse,
    MappingReview,
    MappingStatus,
    MappingSubmission,
    MappingSubmissionCreate,
    OfflineBundle,
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


def admin_actor_from(request: Request) -> str:
    return verify_admin_request(request, settings_from(request))


Repository = Annotated[PublicDataRepository, Depends(repository_from)]
AppSettings = Annotated[Settings, Depends(settings_from)]
AdminActor = Annotated[str, Depends(admin_actor_from)]


def _data_source(repository: PublicDataRepository) -> DataSource:
    manifest = repository.manifest
    return DataSource(
        data_mode=manifest["data_mode"],
        title=str(manifest["title"]),
        provider=str(manifest["provider"]),
        license=str(manifest["license"]),
        catalog_url=str(manifest["catalog_url"]),
        specification_revision=manifest.get("specification_revision"),
        generated_at=manifest.get("generated_at"),
        source_updated_at=manifest.get("source_updated_at"),
        source_map_version=manifest.get("source_map_version"),
        dataset_version=manifest.get("dataset_version"),
    )


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    repository: PublicDataRepository | None = getattr(
        request.app.state, "repository", None
    )
    database_ready = bool(getattr(request.app.state, "database_ready", False))
    if repository is None:
        return HealthResponse(
            status="degraded",
            data_loaded=False,
            database_ready=database_ready,
            error=getattr(request.app.state, "data_error", "データを読み込めません"),
        )
    manifest = repository.manifest
    return HealthResponse(
        status="ok" if database_ready else "degraded",
        data_loaded=True,
        database_ready=database_ready,
        data_mode=manifest["data_mode"],
        dataset_version=manifest.get("dataset_version"),
        node_count=repository.graph.number_of_nodes(),
        link_count=int(manifest["link_count"]),
        gate_count=sum(place.type == "gate" for place in repository.places),
        exit_count=sum(place.type == "exit" for place in repository.places),
        facility_count=len(repository.facilities),
        floors=repository.floors,
        source={
            "title": manifest.get("title"),
            "provider": manifest.get("provider"),
            "license": manifest.get("license"),
            "license_url": manifest.get("license_url"),
            "catalog_url": manifest.get("catalog_url"),
            "specification_revision": manifest.get("specification_revision"),
            "generated_at": manifest.get("generated_at"),
            "source_updated_at": manifest.get("source_updated_at"),
            "source_map_version": manifest.get("source_map_version"),
            "crs": manifest.get("crs"),
            "raw_sha256": manifest.get("raw_resource", {}).get("sha256"),
        },
        warnings=list(manifest.get("warnings", [])),
        error=None if database_ready else "投稿データベースを利用できません。",
    )


@router.get("/gates", response_model=list[Place])
def gates(repository: Repository) -> list[Place]:
    return [place for place in repository.places if place.type == "gate"]


@router.get("/exits", response_model=list[Place])
def exits(repository: Repository) -> list[Place]:
    return [place for place in repository.places if place.type == "exit"]


@router.get("/exits/{exit_id}", response_model=Place)
def exit_detail(exit_id: str, repository: Repository) -> Place:
    place = repository.places_by_id.get(exit_id)
    if place is None or place.type != "exit":
        raise HTTPException(status_code=404, detail="出口が見つかりません。")
    return place


@router.get("/facilities", response_model=list[Facility])
def facilities(
    repository: Repository,
    floor: str | None = Query(default=None, min_length=1, max_length=20),
    category: str | None = Query(default=None, min_length=1, max_length=40),
    query: str | None = Query(default=None, max_length=120),
) -> list[Facility]:
    normalized_query = (query or "").strip().casefold()
    return [
        item
        for item in repository.facilities
        if item.publication_status == "published"
        and (floor is None or item.floor == floor)
        and (category is None or item.category == category)
        and (
            not normalized_query
            or normalized_query in item.name.casefold()
            or normalized_query in (item.description or "").casefold()
        )
    ]


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


@router.get("/offline-bundle", response_model=OfflineBundle)
def offline_bundle(
    repository: Repository,
    settings: AppSettings,
) -> OfflineBundle:
    nodes = [
        {
            "id": str(node_id),
            "lon": attrs["lon"],
            "lat": attrs["lat"],
            "floor": attrs["floor"],
        }
        for node_id, attrs in repository.graph.nodes(data=True)
    ]
    edges: list[dict[str, Any]] = []
    for source, target, _key, attrs in repository.graph.edges(keys=True, data=True):
        edges.append(
            {
                "id": str(attrs["id"]),
                "source": str(source),
                "target": str(target),
                "length_m": float(attrs["length_m"]),
                "link_type": str(attrs["link_type"]),
                "is_vertical": bool(attrs["is_vertical"]),
                "from_floor": str(attrs["from_floor"]),
                "to_floor": str(attrs["to_floor"]),
                "geometry": attrs["geometry"],
            }
        )
    return OfflineBundle(
        version=str(repository.manifest["dataset_version"]),
        generated_at=repository.manifest.get("generated_at"),
        source_updated_at=repository.manifest.get("source_updated_at"),
        walking_speed_m_per_minute=settings.walking_speed_m_per_minute,
        nodes=nodes,
        edges=edges,
        places=repository.places,
        facilities=repository.facilities,
        landmarks=repository.landmarks,
        networks_by_floor={
            floor: FeatureCollection.model_validate(
                repository.network_for_floor(floor)
            )
            for floor in repository.floors
        },
        floor_maps_by_floor={
            floor: FeatureCollection.model_validate(
                repository.floor_map_for_floor(floor)
            )
            for floor in repository.floors
        },
        data_source=_data_source(repository),
    )


def _client_identifier(request: Request, x_client_id: str | None) -> str:
    if x_client_id and 8 <= len(x_client_id) <= 128:
        return x_client_id
    client_host = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("User-Agent", "")[:200]
    return f"fallback:{client_host}:{user_agent}"


@router.post("/mapping-submissions", response_model=MappingSubmission, status_code=201)
def submit_mapping(
    payload: MappingSubmissionCreate,
    request: Request,
    settings: AppSettings,
    x_client_id: str | None = Header(default=None),
) -> MappingSubmission:
    client_hash = hash_client_identifier(
        _client_identifier(request, x_client_id), settings
    )
    try:
        return create_submission(payload, client_hash=client_hash, settings=settings)
    except SubmissionRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc


@router.get("/mapping-submissions/public", response_model=list[MappingSubmission])
def public_mappings(settings: AppSettings) -> list[MappingSubmission]:
    return [
        item.model_copy(
            update={"review_note": "", "reviewed_by": None, "supplemental": None}
        )
        for item in list_submissions(settings, public_only=True)
    ]


@router.post("/admin/session", response_model=AdminSessionResponse)
def create_admin_login(
    payload: AdminSessionCreate,
    response: Response,
    settings: AppSettings,
) -> AdminSessionResponse:
    actor, expires_at = create_development_session(
        response, key=payload.key, settings=settings
    )
    return AdminSessionResponse(
        actor=actor,
        expires_at=expires_at,
        auth_mode=settings.auth_mode,
    )


@router.delete("/admin/session", status_code=204)
def delete_admin_login(response: Response, settings: AppSettings) -> None:
    clear_admin_session(response, settings)


@router.get("/admin/mapping-submissions", response_model=list[MappingSubmission])
def admin_mappings(
    settings: AppSettings,
    _actor: AdminActor,
    status: MappingStatus | None = None,
    category: str | None = Query(default=None, max_length=40),
    floor: str | None = Query(default=None, max_length=20),
    sort: Literal["newest", "oldest", "supports"] = "newest",
) -> list[MappingSubmission]:
    return list_submissions(
        settings,
        status=status,
        category=category,
        floor=floor,
        sort=sort,
    )


@router.get(
    "/admin/mapping-submissions/{submission_id}",
    response_model=AdminSubmissionDetail,
)
def admin_mapping_detail(
    submission_id: int,
    settings: AppSettings,
    _actor: AdminActor,
) -> AdminSubmissionDetail:
    item = get_submission(settings, submission_id)
    if item is None:
        raise HTTPException(status_code=404, detail="投稿が見つかりません。")
    return AdminSubmissionDetail(
        submission=item,
        similar=similar_submissions(settings, item),
        official_nearby=official_nearby(settings, item),
    )


@router.patch(
    "/admin/mapping-submissions/{submission_id}",
    response_model=MappingSubmission,
)
def review_mapping(
    submission_id: int,
    payload: MappingReview,
    settings: AppSettings,
    actor: AdminActor,
) -> MappingSubmission:
    item = review_submission(settings, submission_id, payload, actor)
    if item is None:
        raise HTTPException(status_code=404, detail="投稿が見つかりません。")
    return item


@router.get("/admin/audit-logs", response_model=list[AuditLog])
def audit_logs(
    settings: AppSettings,
    _actor: AdminActor,
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[AuditLog]:
    return list_audit_logs(settings, limit=limit)


@router.get("/admin/export")
def export_submissions(
    settings: AppSettings,
    _actor: AdminActor,
    format: Literal["csv", "json"] = "json",
) -> Response:
    items = list_submissions(settings, sort="newest")
    if format == "json":
        return Response(
            content=json.dumps(
                [item.model_dump(mode="json") for item in items],
                ensure_ascii=False,
                indent=2,
            ),
            media_type="application/json",
            headers={
                "Content-Disposition": 'attachment; filename="mapping-submissions.json"'
            },
        )
    output = io.StringIO()
    fieldnames = list(MappingSubmission.model_fields)
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for item in items:
        writer.writerow(item.model_dump(mode="json"))
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="mapping-submissions.csv"'
        },
    )
