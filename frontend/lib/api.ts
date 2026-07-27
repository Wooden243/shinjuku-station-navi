import type {
  FeatureCollection,
  HealthResponse,
  Place,
  RouteRequest,
  RouteResponse,
} from "@/lib/types";

interface ErrorPayload {
  detail?: string;
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
    response = await fetch(path, {
      ...init,
      headers: {
        Accept: "application/json",
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError(
      "APIに接続できません。FastAPIが起動しているか確認してください。",
      0,
    );
  }

  if (!response.ok) {
    let message = `APIエラー（${response.status}）`;
    try {
      const payload = (await response.json()) as ErrorPayload;
      if (typeof payload.detail === "string") {
        message = payload.detail;
      }
    } catch {
      // JSONでない応答ではHTTPステータス由来のメッセージを維持する。
    }
    throw new ApiError(message, response.status);
  }
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

export function fetchRoute(body: RouteRequest): Promise<RouteResponse> {
  return request<RouteResponse>("/api/routes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
