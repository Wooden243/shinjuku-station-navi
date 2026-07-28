import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Place } from "@/lib/types";

import { ExitInfoCard } from "./ExitInfoCard";

const exit: Place = {
  id: "exit-a8", type: "exit", name: "A8出口", operator: "東京都",
  direction: "", floor: "B1", lon: 139.7, lat: 35.69, node_id: "n2",
  snap_distance_m: 1, source_entity_id: 1, source_geometry_id: 2,
  verified_on_site: false, exit_number: "A8", official_name: "A8出口",
  road_or_direction: null, nearby_landmarks: [{ name: "公開施設", distance_meters: 22 }],
  equipment: [], accessibility: null, available_hours: null, closure_notes: [],
  source: { title: "新宿駅周辺の施設情報等", provider: "東京都都市整備局", url: "https://example.invalid", license: "CC BY 4.0", retrieved_at: "2026-07-28T00:00:00Z" },
  data_updated_at: "2023-02-28T00:00:00Z", verification_status: "not-verified",
  provenance: { official_name: "open-data", floor: "open-data", nearby_landmarks: "derived-open-data", accessibility: "unverified" },
};

describe("ExitInfoCard", () => {
  it("distinguishes missing and unverified values from open data", () => {
    render(<ExitInfoCard exit={exit} />);
    expect(screen.getByText("A8出口", { selector: "strong" })).toBeInTheDocument();
    expect(screen.getAllByText("情報なし").length).toBeGreaterThan(0);
    expect(screen.getAllByText("未確認").length).toBeGreaterThan(0);
    expect(screen.getByText(/公開施設/)).toHaveTextContent("直線約22m");
    expect(screen.getByText("公開データから算出")).toBeInTheDocument();
    expect(screen.getByText(/現地確認は未実施/)).toBeInTheDocument();
  });
});
