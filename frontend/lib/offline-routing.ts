import { apiUrl } from "@/lib/api-url";
import {
  loadOfflineBundle,
  saveOfflineBundle,
  statusFromBundle,
} from "@/lib/offline-storage";
import type {
  FeatureCollection,
  OfflineBundle,
  OfflineDataStatus,
  OfflineEdge,
  RouteRequest,
  RouteResponse,
} from "@/lib/types";

const TRANSITION_LABELS: Record<string, string> = {
  stairs: "階段",
  stair: "階段",
  escalator: "エスカレーター",
  elevator: "エレベーター",
  movingwalkway: "動く歩道",
  ramp: "スロープ",
  vertical: "階層移動設備（種別不明）",
};

function staleWarning(bundle: OfflineBundle): string | null {
  if (!bundle.source_updated_at) {
    return "公開原本の更新日を確認できません。現地の案内を優先してください。";
  }
  const updated = Date.parse(bundle.source_updated_at);
  if (Number.isNaN(updated)) return "公開原本の更新日を解釈できません。";
  const ageDays = (Date.now() - updated) / 86_400_000;
  if (ageDays > 180) {
    return `公開原本の更新から${Math.floor(ageDays)}日以上経過しています。工事・閉鎖・店舗情報は現況と異なる可能性があります。`;
  }
  return null;
}

export async function refreshOfflineData(): Promise<OfflineDataStatus> {
  try {
    const response = await fetch(apiUrl("/api/offline-bundle"), {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const bundle = (await response.json()) as OfflineBundle;
    const stored = await saveOfflineBundle(bundle);
    return { ...stored, warning: stored.warning ?? staleWarning(bundle) };
  } catch (error) {
    const stored = await loadOfflineBundle();
    if (stored.bundle) {
      return {
        ...statusFromBundle(stored.bundle, stored.storage, stored.warning),
        warning:
          stored.warning ??
          staleWarning(stored.bundle) ??
          `更新確認に失敗しました: ${error instanceof Error ? error.message : "通信エラー"}`,
      };
    }
    return {
      available: false,
      version: null,
      generatedAt: null,
      sourceUpdatedAt: null,
      storage: "none",
      warning:
        "オフラインデータがありません。初回は通信可能な状態でアプリを開いてください。",
    };
  }
}

export async function getOfflineBundle(): Promise<OfflineBundle> {
  const stored = await loadOfflineBundle();
  if (stored.bundle) return stored.bundle;
  const status = await refreshOfflineData();
  const refreshed = await loadOfflineBundle();
  if (!refreshed.bundle) {
    throw new Error(
      status.warning ??
        "端末内経路データがありません。初回はオンライン接続が必要です。",
    );
  }
  return refreshed.bundle;
}

export function offlineMapData(
  bundle: OfflineBundle,
  floor: string,
): { network: FeatureCollection; floorMap: FeatureCollection } {
  return {
    network:
      bundle.networks_by_floor[floor] ?? {
        type: "FeatureCollection",
        features: [],
      },
    floorMap:
      bundle.floor_maps_by_floor[floor] ?? {
        type: "FeatureCollection",
        features: [],
      },
  };
}

function cardinalDirection(
  start: [number, number],
  end: [number, number],
): string | null {
  const meanLat = ((start[1] + end[1]) / 2) * (Math.PI / 180);
  const east = (end[0] - start[0]) * Math.cos(meanLat);
  const north = end[1] - start[1];
  if (Math.hypot(east, north) < 0.00003) return null;
  const angle = (Math.atan2(east, north) * 180) / Math.PI;
  const labels = ["北", "北東", "東", "南東", "南", "南西", "西", "北西"];
  return labels[Math.round(((angle + 360) % 360) / 45) % 8];
}

function lineEndpoints(edge: OfflineEdge): {
  start: [number, number];
  end: [number, number];
} | null {
  const coordinates = edge.geometry.coordinates;
  if (coordinates.length < 2) return null;
  return {
    start: coordinates[0] as [number, number],
    end: coordinates.at(-1) as [number, number],
  };
}

export function calculateOfflineRouteFromBundle(
  bundle: OfflineBundle,
  request: RouteRequest,
): RouteResponse {
  const start = bundle.places.find(
    (place) => place.id === request.start_gate_id && place.type === "gate",
  );
  const destination = bundle.places.find(
    (place) =>
      place.id === request.destination_exit_id && place.type === "exit",
  );
  if (!start || !destination) {
    throw new Error("端末内データに選択地点がありません。");
  }

  const adjacency = new Map<string, OfflineEdge[]>();
  for (const edge of bundle.edges) {
    if (
      request.preferences.avoid_stairs &&
      ["stairs", "stair"].includes(edge.link_type.toLowerCase())
    ) {
      continue;
    }
    const list = adjacency.get(edge.source) ?? [];
    list.push(edge);
    adjacency.set(edge.source, list);
  }
  for (const edges of adjacency.values()) {
    edges.sort(
      (left, right) =>
        left.length_m - right.length_m || left.id.localeCompare(right.id),
    );
  }

  const distance = new Map<string, number>([[start.node_id, 0]]);
  const previous = new Map<string, OfflineEdge>();
  const pending = new Set<string>([start.node_id]);
  while (pending.size > 0) {
    let current = "";
    let best = Number.POSITIVE_INFINITY;
    for (const candidate of pending) {
      const value = distance.get(candidate) ?? Number.POSITIVE_INFINITY;
      if (
        value < best ||
        (value === best && (current === "" || candidate.localeCompare(current) < 0))
      ) {
        current = candidate;
        best = value;
      }
    }
    pending.delete(current);
    if (current === destination.node_id) break;
    for (const edge of adjacency.get(current) ?? []) {
      const next = best + edge.length_m;
      const existing = distance.get(edge.target) ?? Number.POSITIVE_INFINITY;
      const previousEdge = previous.get(edge.target);
      if (
        next < existing ||
        (next === existing &&
          (!previousEdge || edge.id.localeCompare(previousEdge.id) < 0))
      ) {
        distance.set(edge.target, next);
        previous.set(edge.target, edge);
        pending.add(edge.target);
      }
    }
  }
  if (!distance.has(destination.node_id)) {
    throw new Error("指定条件で到達できる経路がありません。");
  }

  const edges: OfflineEdge[] = [];
  const pathNodes = [destination.node_id];
  let cursor = destination.node_id;
  while (cursor !== start.node_id) {
    const edge = previous.get(cursor);
    if (!edge) throw new Error("オフライン経路を復元できません。");
    edges.unshift(edge);
    cursor = edge.source;
    pathNodes.unshift(cursor);
  }

  const routeByFloor: Record<string, FeatureCollection> = {};
  const floors: string[] = [start.floor];
  const transitions: RouteResponse["floor_transitions"] = [];
  edges.forEach((edge, sequence) => {
    const feature: GeoJSON.Feature<GeoJSON.LineString, Record<string, unknown>> = {
      type: "Feature",
      properties: {
        id: edge.id,
        sequence,
        from_node: edge.source,
        to_node: edge.target,
        direction: "start-to-destination",
        link_type: edge.link_type,
        is_transition: edge.from_floor !== edge.to_floor || edge.is_vertical,
      },
      geometry: edge.geometry,
    };
    const edgeFloors =
      edge.from_floor === edge.to_floor
        ? [edge.from_floor]
        : [edge.from_floor, edge.to_floor];
    for (const floor of edgeFloors) {
      if (!floors.includes(floor)) floors.push(floor);
      const collection = routeByFloor[floor] ?? {
        type: "FeatureCollection",
        features: [],
      };
      collection.features.push({
        ...feature,
        properties: { ...feature.properties, floor },
      });
      routeByFloor[floor] = collection;
    }
    if (edge.from_floor !== edge.to_floor || edge.is_vertical) {
      const endpoints = lineEndpoints(edge);
      transitions.push({
        from_floor: edge.from_floor,
        to_floor: edge.to_floor,
        type: edge.link_type,
        label:
          TRANSITION_LABELS[edge.link_type.toLowerCase()] ??
          "階層移動設備（種別不明）",
        coordinate: endpoints?.end ?? [start.lon, start.lat],
      });
    }
  });

  const instructions: RouteResponse["instructions"] = [
    {
      order: 1,
      floor: start.floor,
      text: `${start.name}を出発し、地図上の矢印に沿って進みます。`,
      distance_meters: null,
      transition_type: null,
      coordinate: [start.lon, start.lat],
    },
  ];
  let order = 2;
  let accumulated = 0;
  let segmentStart: [number, number] | null = null;
  let segmentEnd: [number, number] | null = null;
  let segmentFloor = start.floor;
  const flushSegment = () => {
    if (accumulated <= 0) return;
    const direction =
      accumulated >= 15 && segmentStart && segmentEnd
        ? cardinalDirection(segmentStart, segmentEnd)
        : null;
    instructions.push({
      order,
      floor: segmentFloor,
      text: `${direction ? `${direction}へ` : `${segmentFloor}を`}約${Math.round(accumulated)}メートル進みます。`,
      distance_meters: Math.round(accumulated * 10) / 10,
      transition_type: null,
      coordinate: segmentEnd,
    });
    order += 1;
    accumulated = 0;
    segmentStart = null;
    segmentEnd = null;
  };
  for (const edge of edges) {
    const isTransition = edge.from_floor !== edge.to_floor || edge.is_vertical;
    const endpoints = lineEndpoints(edge);
    if (isTransition) {
      flushSegment();
      const label =
        TRANSITION_LABELS[edge.link_type.toLowerCase()] ??
        "階層移動設備（種別不明）";
      instructions.push({
        order,
        floor: edge.from_floor,
        text: `${label}で${edge.from_floor}から${edge.to_floor}へ移動します。`,
        distance_meters: edge.length_m,
        transition_type: edge.link_type,
        coordinate: endpoints?.end ?? null,
      });
      order += 1;
      segmentFloor = edge.to_floor;
    } else {
      segmentStart ??= endpoints?.start ?? null;
      segmentEnd = endpoints?.end ?? segmentEnd;
      segmentFloor = edge.from_floor;
      accumulated += edge.length_m;
    }
  }
  flushSegment();
  instructions.push({
    order,
    floor: destination.floor,
    text: `${destination.name}から地上へ出ます。現地の案内表示と通行状況を確認してください。`,
    distance_meters: null,
    transition_type: null,
    coordinate: [destination.lon, destination.lat],
  });

  const total = distance.get(destination.node_id) ?? 0;
  const routeLandmarks = bundle.landmarks.filter((item) =>
    pathNodes.includes(item.node_id),
  );
  return {
    route_id: `offline-${bundle.version}-${start.id}-${destination.id}-${request.preferences.avoid_stairs}`,
    start_gate: start,
    destination_exit: destination,
    distance_meters: Math.round(total * 10) / 10,
    estimated_walking_minutes:
      Math.round((total / bundle.walking_speed_m_per_minute) * 10) / 10,
    floors,
    floor_transitions: transitions,
    route_by_floor: routeByFloor,
    instructions,
    landmarks: routeLandmarks,
    warnings: [
      "通信できないため、端末に保存済みの公開データで経路を計算しました。",
      staleWarning(bundle) ??
        "工事・閉鎖・営業時間などの最新情報は現地で確認してください。",
      "現地の案内表示と係員の指示を優先してください。",
    ],
    data_source: bundle.data_source,
  };
}

export async function calculateOfflineRoute(
  request: RouteRequest,
): Promise<RouteResponse> {
  return calculateOfflineRouteFromBundle(await getOfflineBundle(), request);
}
