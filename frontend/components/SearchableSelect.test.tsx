import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Place } from "@/lib/types";

import { SearchableSelect } from "./SearchableSelect";

function place(overrides: Partial<Place>): Place {
  return {
    id: "gate-1", type: "gate", name: "中央東改札", operator: "JR東日本",
    direction: "東口方面", floor: "B1", lon: 139.7, lat: 35.69,
    node_id: "node-1", snap_distance_m: 1.2, source_entity_id: 10,
    source_geometry_id: 1759781, verified_on_site: false, exit_number: null,
    official_name: null, road_or_direction: null, nearby_landmarks: [],
    equipment: [], accessibility: null, available_hours: null, closure_notes: [],
    source: null, data_updated_at: null, verification_status: "not-verified",
    provenance: {},
    ...overrides,
  };
}

const places = [
  place({}),
  place({ id: "gate-2", name: "西口改札", operator: "都営地下鉄", direction: "西口方面", lon: 139.69, node_id: "node-2" }),
];

describe("SearchableSelect", () => {
  it("filters by operator and keeps distinguishing metadata", () => {
    const onChange = vi.fn();
    render(<SearchableSelect id="gate" label="出発改札" places={places} value="gate-1" onChange={onChange} />);
    fireEvent.change(screen.getByPlaceholderText("出発改札を検索"), { target: { value: "都営" } });
    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(1);
    expect(options[0]).toHaveTextContent("西口改札");
    expect(options[0]).toHaveTextContent("都営地下鉄");
    expect(options[0]).toHaveTextContent("B1");
    expect(onChange).toHaveBeenCalledWith("gate-2");
  });

  it("clears the selected place when the search has no matches", () => {
    const onChange = vi.fn();
    render(<SearchableSelect id="gate" label="出発改札" places={places} value="gate-1" onChange={onChange} />);
    fireEvent.change(screen.getByPlaceholderText("出発改札を検索"), { target: { value: "存在しない地点" } });
    expect(screen.getAllByRole("option")).toHaveLength(1);
    expect(screen.getByRole("option")).toHaveTextContent("一致する地点がありません");
    expect(onChange).toHaveBeenCalledWith("");
  });
});
