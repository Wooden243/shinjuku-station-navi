import { describe, expect, it } from "vitest";

import type { RouteResponse } from "@/lib/types";

import { sanitizeRouteForFloor } from "./MapView";

const route = {
  route_id: "r1",
  route_by_floor: {
    B1: {
      type: "FeatureCollection",
      features: [
        { type: "Feature", properties: { sequence: 2, is_transition: true }, geometry: { type: "LineString", coordinates: [[3, 3], [4, 4]] } },
        { type: "Feature", properties: { sequence: 1, direction: "start-to-destination" }, geometry: { type: "LineString", coordinates: [[1, 1], [1, 1], [2, 2]] } },
      ],
    },
  },
} as unknown as RouteResponse;

describe("route arrow data", () => {
  it("keeps coordinate order, removes duplicates, and excludes transitions from arrows", () => {
    const arrows = sanitizeRouteForFloor(route, "B1", true);
    expect(arrows.features).toHaveLength(1);
    expect(arrows.features[0].properties?.direction).toBe("start-to-destination");
    expect((arrows.features[0].geometry as GeoJSON.LineString).coordinates).toEqual([[1, 1], [2, 2]]);
  });

  it("deletes old arrows when no route remains", () => {
    expect(sanitizeRouteForFloor(null, "B1", true).features).toEqual([]);
  });
});
