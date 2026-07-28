import { apiUrl } from "@/lib/api-url";
import { getAnonymousClientId } from "@/lib/offline-storage";
import {
  calculateOfflineRoute,
  getOfflineBundle,
  offlineMapData,
} from "@/lib/offline-routing";
import type {
  AdminSubmissionDetail,
  AuditLog,
  Facility,
  FeatureCollection,
  HealthResponse,
  MappingStatus,
  MappingSubmission,
  MappingSubmissionCreate,
  OfflineBundle,
  Place,
  RouteRequest,
  RouteResponse,
} from "@/lib/types";

interface ErrorPayload {
  detail?: string | Array<{ msg?: string }>;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      credentials: "include",
      ...init,
      headers: {
        Accept: "application/json",
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError("APIに接続できません。保存済みデータを確認します。", 0);
  }

  if (!response.ok) {
    let message = `APIエラー（${response.status}）`;
    try {
      const payload = (await response.json()) as ErrorPayload;
      if (typeof payload.detail === "string") {
        message = payload.detail;
      } else if (Array.isArray(payload.detail)) {
        message = payload.detail
          .map((item) => item.msg)
          .filter(Boolean)
          .join(" / ");
      }
    } catch {
      // JSONでない応答ではHTTPステータス由来のメッセージを維持する。
    }
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health");
}

export function fetchGates(): Promise<Place[]> {
  return request<Place[]>("/api/gates");
}

export function fetchExits(): Promise<Place[]> {
  return request<Place[]>("/api/exits");
}

export function fetchFacilities(): Promise<Facility[]> {
  return request<Facility[]>("/api/facilities");
}

export function fetchNetwork(floor: string): Promise<FeatureCollection> {
  return request<FeatureCollection>(
    `/api/network?floor=${encodeURIComponent(floor)}`,
  );
}

export function fetchFloorMap(floor: string): Promise<FeatureCollection> {
  return request<FeatureCollection>(
    `/api/floor-map?floor=${encodeURIComponent(floor)}`,
  );
}

export interface BootstrapData {
  health: HealthResponse;
  gates: Place[];
  exits: Place[];
  facilities: Facility[];
  bundle: OfflineBundle | null;
  offline: boolean;
}

function healthFromBundle(bundle: OfflineBundle): HealthResponse {
  return {
    status: "degraded",
    data_loaded: true,
    database_ready: false,
    data_mode: bundle.data_source.data_mode,
    dataset_version: bundle.version,
    node_count: bundle.nodes.length,
    link_count: bundle.edges.length,
    gate_count: bundle.places.filter((item) => item.type === "gate").length,
    exit_count: bundle.places.filter((item) => item.type === "exit").length,
    facility_count: bundle.facilities.length,
    floors: Object.keys(bundle.networks_by_floor),
    source: {
      title: bundle.data_source.title,
      provider: bundle.data_source.provider,
      license: bundle.data_source.license,
      catalog_url: bundle.data_source.catalog_url,
      generated_at: bundle.generated_at ?? undefined,
      source_updated_at: bundle.source_updated_at ?? undefined,
      source_map_version: bundle.data_source.source_map_version ?? undefined,
      crs: bundle.data_source.crs,
    },
    warnings: ["端末に保存済みの公開データを表示しています。"],
    error: "オフラインのため投稿・更新確認は利用できません。",
  };
}

export async function fetchBootstrapData(): Promise<BootstrapData> {
  try {
    const [health, gates, exits, facilities] = await Promise.all([
      fetchHealth(),
      fetchGates(),
      fetchExits(),
      fetchFacilities(),
    ]);
    return { health, gates, exits, facilities, bundle: null, offline: false };
  } catch (error) {
    const bundle = await getOfflineBundle();
    if (!bundle) throw error;
    return {
      health: healthFromBundle(bundle),
      gates: bundle.places.filter((item) => item.type === "gate"),
      exits: bundle.places.filter((item) => item.type === "exit"),
      facilities: bundle.facilities,
      bundle,
      offline: true,
    };
  }
}

export async function fetchMapData(
  floor: string,
  knownBundle: OfflineBundle | null,
): Promise<{
  network: FeatureCollection;
  floorMap: FeatureCollection;
  bundle: OfflineBundle | null;
  offline: boolean;
}> {
  try {
    const [network, floorMap] = await Promise.all([
      fetchNetwork(floor),
      fetchFloorMap(floor),
    ]);
    return { network, floorMap, bundle: knownBundle, offline: false };
  } catch {
    const bundle = knownBundle ?? (await getOfflineBundle());
    return { ...offlineMapData(bundle, floor), bundle, offline: true };
  }
}

export async function fetchRoute(body: RouteRequest): Promise<RouteResponse> {
  try {
    return await request<RouteResponse>("/api/routes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (error) {
    if (
      error instanceof ApiError &&
      error.status !== 0 &&
      error.status < 500
    ) {
      throw error;
    }
    return calculateOfflineRoute(body);
  }
}

export function fetchPublicMappings(): Promise<MappingSubmission[]> {
  return request<MappingSubmission[]>("/api/mapping-submissions/public");
}

export function submitMapping(
  body: MappingSubmissionCreate,
): Promise<MappingSubmission> {
  return request<MappingSubmission>("/api/mapping-submissions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Client-Id": getAnonymousClientId(),
    },
    body: JSON.stringify(body),
  });
}

export function createAdminSession(
  key: string,
): Promise<{ actor: string; expires_at: string; auth_mode: string }> {
  return request("/api/admin/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key }),
  });
}

export function deleteAdminSession(): Promise<void> {
  return request<void>("/api/admin/session", { method: "DELETE" });
}

export interface AdminFilters {
  status?: MappingStatus | "";
  category?: string;
  floor?: string;
  sort?: "newest" | "oldest" | "supports";
}

export function fetchAdminMappings(
  filters: AdminFilters = {},
): Promise<MappingSubmission[]> {
  const query = new URLSearchParams();
  if (filters.status) query.set("status", filters.status);
  if (filters.category) query.set("category", filters.category);
  if (filters.floor) query.set("floor", filters.floor);
  if (filters.sort) query.set("sort", filters.sort);
  return request<MappingSubmission[]>(
    `/api/admin/mapping-submissions?${query.toString()}`,
  );
}

export function fetchAdminMappingDetail(
  id: number,
): Promise<AdminSubmissionDetail> {
  return request<AdminSubmissionDetail>(`/api/admin/mapping-submissions/${id}`);
}

export function reviewMapping(
  id: number,
  body: {
    status: MappingStatus;
    review_note: string;
    category?: string;
    name?: string;
    description?: string;
    floor?: string;
    lon?: number;
    lat?: number;
  },
): Promise<MappingSubmission> {
  return request<MappingSubmission>(`/api/admin/mapping-submissions/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function fetchAuditLogs(): Promise<AuditLog[]> {
  return request<AuditLog[]>("/api/admin/audit-logs");
}
