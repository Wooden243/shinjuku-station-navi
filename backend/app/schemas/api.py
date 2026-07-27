from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Floor = str
PlaceType = Literal["gate", "exit"]
DataMode = Literal["open-data", "fixture"]


class Place(BaseModel):
    id: str
    type: PlaceType
    name: str
    operator: str
    direction: str
    floor: Floor
    lon: float
    lat: float
    node_id: str
    snap_distance_m: float
    source_entity_id: int | None = None
    source_geometry_id: int | None = None
    verified_on_site: bool = False


class RoutePreferences(BaseModel):
    avoid_stairs: bool = False


class RouteRequest(BaseModel):
    start_gate_id: str = Field(min_length=1, max_length=200)
    destination_exit_id: str = Field(min_length=1, max_length=200)
    preferences: RoutePreferences = Field(default_factory=RoutePreferences)


class Instruction(BaseModel):
    order: int
    floor: Floor
    text: str
    distance_meters: float | None = None
    transition_type: str | None = None
    coordinate: list[float] | None = None


class FloorTransition(BaseModel):
    from_floor: Floor
    to_floor: Floor
    type: str
    label: str
    coordinate: list[float]


class Landmark(BaseModel):
    id: str
    node_id: str
    name: str
    description: str
    floor: Floor
    lon: float
    lat: float
    photo_url: str | None = None
    plateau_url: str | None = None
    is_sample: bool = False


class FeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[dict[str, Any]]


class DataSource(BaseModel):
    data_mode: DataMode
    title: str
    provider: str
    license: str
    catalog_url: str
    specification_revision: str | None = None
    generated_at: str | None = None
    source_map_version: int | None = None
    crs: Literal["EPSG:4326"] = "EPSG:4326"


class RouteResponse(BaseModel):
    route_id: str
    start_gate: Place
    destination_exit: Place
    distance_meters: float
    estimated_walking_minutes: float
    floors: list[Floor]
    floor_transitions: list[FloorTransition]
    route_by_floor: dict[Floor, FeatureCollection]
    instructions: list[Instruction]
    landmarks: list[Landmark]
    warnings: list[str]
    data_source: DataSource


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    data_loaded: bool
    data_mode: DataMode | None = None
    node_count: int = 0
    link_count: int = 0
    gate_count: int = 0
    exit_count: int = 0
    floors: list[Floor] = Field(default_factory=list)
    source: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None

