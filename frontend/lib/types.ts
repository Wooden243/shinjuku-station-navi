export type DataMode = "open-data" | "fixture";
export type PlaceType = "gate" | "exit";

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
}

export type FeatureCollection = GeoJSON.FeatureCollection<
  GeoJSON.Geometry,
  Record<string, unknown>
>;

export interface HealthResponse {
  status: "ok" | "degraded";
  data_loaded: boolean;
  data_mode: DataMode | null;
  node_count: number;
  link_count: number;
  gate_count: number;
  exit_count: number;
  floors: string[];
  source: {
    title?: string;
    provider?: string;
    license?: string;
    license_url?: string;
    catalog_url?: string;
    specification_revision?: string;
    generated_at?: string;
    source_map_version?: number;
    crs?: string;
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
  data_source: {
    data_mode: DataMode;
    title: string;
    provider: string;
    license: string;
    catalog_url: string;
    specification_revision: string | null;
    generated_at: string | null;
    source_map_version: number | null;
    crs: "EPSG:4326";
  };
}

export interface RouteRequest {
  start_gate_id: string;
  destination_exit_id: string;
  preferences: {
    avoid_stairs: boolean;
  };
}
