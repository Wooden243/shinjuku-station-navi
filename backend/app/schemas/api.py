from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

Floor = str
PlaceType = Literal["gate", "exit"]
DataMode = Literal["open-data", "fixture"]
ProvenanceKind = Literal[
    "open-data",
    "derived-open-data",
    "operator-verified",
    "admin-correction",
    "user-submission",
    "unverified",
    "no-data",
]
FacilityCategory = Literal[
    "restaurant",
    "convenience_store",
    "cafe",
    "drugstore",
    "atm",
    "toilet",
    "coin_locker",
    "information",
    "public_phone",
    "elevator",
    "escalator",
    "stairs",
    "meeting_point",
    "shop",
    "other",
]
MappingCategory = Literal[
    "shop",
    "facility_add",
    "name_correction",
    "exit_note",
    "landmark",
    "closure",
    "relocation",
    "passage_closure",
    "construction",
    "accessibility",
    "other",
]
MappingStatus = Literal[
    "pending", "approved", "rejected", "needs_verification", "archived"
]


class SourceReference(BaseModel):
    title: str
    provider: str
    url: str
    license: str
    retrieved_at: str


class NearbyLandmark(BaseModel):
    name: str
    distance_meters: float


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
    exit_number: str | None = None
    official_name: str | None = None
    road_or_direction: str | None = None
    nearby_landmarks: list[NearbyLandmark] = Field(default_factory=list)
    equipment: list[str] = Field(default_factory=list)
    accessibility: str | None = None
    available_hours: str | None = None
    closure_notes: list[str] = Field(default_factory=list)
    source: SourceReference | None = None
    data_updated_at: str | None = None
    verification_status: Literal["not-verified", "verified-on-site"] = "not-verified"
    provenance: dict[str, ProvenanceKind] = Field(default_factory=dict)


class Facility(BaseModel):
    id: str
    name: str
    category: FacilityCategory
    floor: Floor
    lon: float
    lat: float
    description: str | None = None
    hours: str | None = None
    payment_notes: str | None = None
    phone: str | None = None
    url: str | None = None
    public_category: str | None = None
    source_entity_id: int | None = None
    source_geometry_id: int | None = None
    source: SourceReference
    data_updated_at: str | None = None
    publication_status: Literal["published", "hidden"]
    verification_status: Literal["not-verified", "verified-on-site"]
    support_count: int = 0
    is_sample: bool = False
    provenance: dict[str, ProvenanceKind] = Field(default_factory=dict)


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
    source_updated_at: str | None = None
    source_map_version: int | None = None
    dataset_version: str | None = None
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
    database_ready: bool = False
    data_mode: DataMode | None = None
    dataset_version: str | None = None
    node_count: int = 0
    link_count: int = 0
    gate_count: int = 0
    exit_count: int = 0
    facility_count: int = 0
    floors: list[Floor] = Field(default_factory=list)
    source: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


def _plain_text(value: str) -> str:
    normalized = " ".join(value.strip().split())
    if re.search(r"<\s*/?\s*[a-zA-Z!][^>]*>", normalized):
        raise ValueError("HTMLタグは入力できません")
    if any(ord(character) < 32 and character not in "\t\n\r" for character in value):
        raise ValueError("制御文字は入力できません")
    return normalized


class MappingSubmissionCreate(BaseModel):
    client_submission_id: str = Field(
        default_factory=lambda: str(uuid4()), min_length=8, max_length=64
    )
    category: MappingCategory
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=3, max_length=1000)
    floor: Floor = Field(min_length=1, max_length=20)
    lon: float = Field(ge=139.65, le=139.75)
    lat: float = Field(ge=35.65, le=35.75)
    source_method: str = Field(min_length=2, max_length=240)
    supplemental: str | None = Field(default=None, max_length=500)
    observed_at: datetime | None = None

    @field_validator("name", "description", "source_method", "supplemental")
    @classmethod
    def validate_plain_text(cls, value: str | None) -> str | None:
        return None if value is None else _plain_text(value)


class MappingSubmission(BaseModel):
    id: int
    client_submission_id: str
    category: MappingCategory
    name: str
    description: str
    floor: Floor
    lon: float
    lat: float
    source_method: str
    supplemental: str | None
    observed_at: datetime | None
    status: MappingStatus
    review_note: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    support_count: int


class MappingReview(BaseModel):
    status: MappingStatus
    review_note: str = Field(min_length=1, max_length=1000)
    category: MappingCategory | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, min_length=3, max_length=1000)
    floor: Floor | None = Field(default=None, min_length=1, max_length=20)
    lon: float | None = Field(default=None, ge=139.65, le=139.75)
    lat: float | None = Field(default=None, ge=35.65, le=35.75)

    @field_validator("name", "description", "review_note")
    @classmethod
    def validate_review_text(cls, value: str | None) -> str | None:
        return None if value is None else _plain_text(value)


class AuditLog(BaseModel):
    id: int
    submission_id: int | None
    action: str
    actor: str
    details: dict[str, Any]
    created_at: datetime


class AdminSessionCreate(BaseModel):
    key: str = Field(min_length=1, max_length=500)


class AdminSessionResponse(BaseModel):
    authenticated: Literal[True] = True
    actor: str
    expires_at: datetime
    auth_mode: str


class OfficialComparison(BaseModel):
    id: str
    kind: str
    name: str
    floor: str
    distance_meters: float


class AdminSubmissionDetail(BaseModel):
    submission: MappingSubmission
    similar: list[MappingSubmission]
    official_nearby: list[OfficialComparison]


class OfflineBundle(BaseModel):
    version: str
    generated_at: str | None
    source_updated_at: str | None
    route_spec_version: Literal["1.0"] = "1.0"
    walking_speed_m_per_minute: float
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    places: list[Place]
    facilities: list[Facility]
    landmarks: list[Landmark]
    networks_by_floor: dict[Floor, FeatureCollection]
    floor_maps_by_floor: dict[Floor, FeatureCollection]
    data_source: DataSource
