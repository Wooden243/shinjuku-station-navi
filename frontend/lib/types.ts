export type DataMode = "open-data" | "fixture";
export type PlaceType = "gate" | "exit";
export type ProvenanceKind =
  | "open-data"
  | "derived-open-data"
  | "operator-verified"
  | "admin-correction"
  | "user-submission"
  | "unverified"
  | "no-data";

export interface SourceReference {
  title: string;
  provider: string;
  url: string;
  license: string;
  retrieved_at: string;
}

export interface NearbyLandmark {
  name: string;
  distance_meters: number;
}

export interface Place {
  id: string;
  type: PlaceType;
  name: string;
  operator: string;
  direction: string;
  floor: string;
  lon: number;
  lat: number;
  node_id: string;
  snap_distance_m: number;
  source_entity_id: number | null;
  source_geometry_id: number | null;
  verified_on_site: boolean;
  exit_number: string | null;
  official_name: string | null;
  road_or_direction: string | null;
  nearby_landmarks: NearbyLandmark[];
  equipment: string[];
  accessibility: string | null;
  available_hours: string | null;
  closure_notes: string[];
  source: SourceReference | null;
  data_updated_at: string | null;
  verification_status: "not-verified" | "verified-on-site";
  provenance: Record<string, ProvenanceKind>;
}

export type FacilityCategory =
  | "restaurant"
  | "convenience_store"
  | "cafe"
  | "drugstore"
  | "atm"
  | "toilet"
  | "coin_locker"
  | "information"
  | "public_phone"
  | "elevator"
  | "escalator"
  | "stairs"
  | "meeting_point"
  | "shop"
  | "other";

export interface Facility {
  id: string;
  name: string;
  category: FacilityCategory;
  floor: string;
  lon: number;
  lat: number;
  description: string | null;
  hours: string | null;
  payment_notes: string | null;
  phone: string | null;
  url: string | null;
  public_category: string | null;
  source_entity_id: number | null;
  source_geometry_id: number | null;
  source: SourceReference;
  data_updated_at: string | null;
  publication_status: "published" | "hidden";
  verification_status: "not-verified" | "verified-on-site";
  support_count: number;
  is_sample: boolean;
  provenance: Record<string, ProvenanceKind>;
}

export type FeatureCollection = GeoJSON.FeatureCollection<
  GeoJSON.Geometry,
  Record<string, unknown>
>;

export interface DataSource {
  data_mode: DataMode;
  title: string;
  provider: string;
  license: string;
  catalog_url: string;
  specification_revision: string | null;
  generated_at: string | null;
  source_updated_at: string | null;
  source_map_version: number | null;
  dataset_version: string | null;
  crs: "EPSG:4326";
}

export interface HealthResponse {
  status: "ok" | "degraded";
  data_loaded: boolean;
  database_ready: boolean;
  data_mode: DataMode | null;
  dataset_version: string | null;
  node_count: number;
  link_count: number;
  gate_count: number;
  exit_count: number;
  facility_count: number;
  floors: string[];
  source: {
    title?: string;
    provider?: string;
    license?: string;
    license_url?: string;
    catalog_url?: string;
    specification_revision?: string;
    generated_at?: string;
    source_updated_at?: string;
    source_map_version?: number;
    crs?: string;
    raw_sha256?: string;
  };
  warnings: string[];
  error: string | null;
}

export interface FloorTransition {
  from_floor: string;
  to_floor: string;
  type: string;
  label: string;
  coordinate: number[];
}

export interface Instruction {
  order: number;
  floor: string;
  text: string;
  distance_meters: number | null;
  transition_type: string | null;
  coordinate: number[] | null;
}

export interface Landmark {
  id: string;
  node_id: string;
  name: string;
  description: string;
  floor: string;
  lon: number;
  lat: number;
  photo_url: string | null;
  plateau_url: string | null;
  is_sample: boolean;
}

export interface RouteResponse {
  route_id: string;
  start_gate: Place;
  destination_exit: Place;
  distance_meters: number;
  estimated_walking_minutes: number;
  floors: string[];
  floor_transitions: FloorTransition[];
  route_by_floor: Record<string, FeatureCollection>;
  instructions: Instruction[];
  landmarks: Landmark[];
  warnings: string[];
  data_source: DataSource;
}

export interface RouteRequest {
  start_gate_id: string;
  destination_exit_id: string;
  preferences: {
    avoid_stairs: boolean;
  };
}

export interface OfflineEdge {
  id: string;
  source: string;
  target: string;
  length_m: number;
  link_type: string;
  is_vertical: boolean;
  from_floor: string;
  to_floor: string;
  geometry: GeoJSON.LineString;
}

export interface OfflineBundle {
  version: string;
  generated_at: string | null;
  source_updated_at: string | null;
  route_spec_version: "1.0";
  walking_speed_m_per_minute: number;
  nodes: Array<{ id: string; lon: number; lat: number; floor: string }>;
  edges: OfflineEdge[];
  places: Place[];
  facilities: Facility[];
  landmarks: Landmark[];
  networks_by_floor: Record<string, FeatureCollection>;
  floor_maps_by_floor: Record<string, FeatureCollection>;
  data_source: DataSource;
}

export type MappingCategory =
  | "shop"
  | "facility_add"
  | "name_correction"
  | "exit_note"
  | "landmark"
  | "closure"
  | "relocation"
  | "passage_closure"
  | "construction"
  | "accessibility"
  | "other";

export type MappingStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "needs_verification"
  | "archived";

export interface MappingSubmission {
  id: number;
  client_submission_id: string;
  category: MappingCategory;
  name: string;
  description: string;
  floor: string;
  lon: number;
  lat: number;
  source_method: string;
  supplemental: string | null;
  observed_at: string | null;
  status: MappingStatus;
  review_note: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
  support_count: number;
}

export type MappingSubmissionCreate = Omit<
  MappingSubmission,
  | "id"
  | "status"
  | "review_note"
  | "reviewed_by"
  | "reviewed_at"
  | "created_at"
  | "updated_at"
  | "support_count"
>;

export interface AuditLog {
  id: number;
  submission_id: number | null;
  action: string;
  actor: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface OfficialComparison {
  id: string;
  kind: string;
  name: string;
  floor: string;
  distance_meters: number;
}

export interface AdminSubmissionDetail {
  submission: MappingSubmission;
  similar: MappingSubmission[];
  official_nearby: OfficialComparison[];
}

export interface OfflineDataStatus {
  available: boolean;
  version: string | null;
  generatedAt: string | null;
  sourceUpdatedAt: string | null;
  storage: "indexeddb" | "cache" | "memory" | "none";
  warning: string | null;
}
