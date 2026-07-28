import { describe, expect, it } from "vitest";

import type { OfflineBundle, Place } from "./types";
import { calculateOfflineRouteFromBundle } from "./offline-routing";

const common = {
  operator: "東京都", direction: "", floor: "B1", snap_distance_m: 0,
  source_entity_id: null, source_geometry_id: null, verified_on_site: false,
  exit_number: null, official_name: null, road_or_direction: null,
  nearby_landmarks: [], equipment: [], accessibility: null, available_hours: null,
  closure_notes: [], source: null, data_updated_at: null,
  verification_status: "not-verified" as const, provenance: {},
};
const start: Place = { ...common, id: "g", type: "gate", name: "改札", lon: 139.7, lat: 35.69, node_id: "n1" };
const goal: Place = { ...common, id: "e", type: "exit", name: "A1出口", lon: 139.7002, lat: 35.69, node_id: "n2" };
const bundle: OfflineBundle = {
  version: "v1", generated_at: "2026-07-28T00:00:00Z", source_updated_at: "2023-02-28T00:00:00Z",
  route_spec_version: "1.0", walking_speed_m_per_minute: 80,
  nodes: [{ id: "n1", lon: start.lon, lat: start.lat, floor: "B1" }, { id: "n2", lon: goal.lon, lat: goal.lat, floor: "B1" }],
  edges: [{ id: "edge", source: "n1", target: "n2", length_m: 20, link_type: "walkway", is_vertical: false, from_floor: "B1", to_floor: "B1", geometry: { type: "LineString", coordinates: [[start.lon, start.lat], [goal.lon, goal.lat]] } }],
  places: [start, goal], facilities: [], landmarks: [],
  networks_by_floor: { B1: { type: "FeatureCollection", features: [] } },
  floor_maps_by_floor: { B1: { type: "FeatureCollection", features: [] } },
  data_source: { data_mode: "open-data", title: "dataset", provider: "東京都", license: "CC BY", catalog_url: "https://example.invalid", specification_revision: null, generated_at: null, source_updated_at: null, source_map_version: null, dataset_version: "v1", crs: "EPSG:4326" },
};

describe("offline routing", () => {
  it("uses the stored directed graph and preserves start-to-destination coordinates", () => {
    const result = calculateOfflineRouteFromBundle(bundle, { start_gate_id: "g", destination_exit_id: "e", preferences: { avoid_stairs: false } });
    expect(result.distance_meters).toBe(20);
    expect(result.estimated_walking_minutes).toBe(0.3);
    const feature = result.route_by_floor.B1.features[0];
    expect(feature.properties?.direction).toBe("start-to-destination");
    expect((feature.geometry as GeoJSON.LineString).coordinates[0]).toEqual([start.lon, start.lat]);
    expect(result.instructions.some((item) => item.text.includes("東"))).toBe(true);
  });

  it("does not fabricate a route for a disconnected destination", () => {
    expect(() => calculateOfflineRouteFromBundle({ ...bundle, edges: [] }, { start_gate_id: "g", destination_exit_id: "e", preferences: { avoid_stairs: false } })).toThrow(/到達できる経路/);
  });
});
