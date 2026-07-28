"use client";

import { useEffect, useRef } from "react";
import maplibregl, {
  type GeoJSONSource,
  type Map as MapLibreMap,
  type Marker,
  type StyleSpecification,
} from "maplibre-gl";

import { FACILITY_META } from "@/lib/facilities";
import type {
  Facility,
  FeatureCollection,
  FloorTransition,
  MappingSubmission,
  Place,
  RouteResponse,
} from "@/lib/types";

import styles from "./MapView.module.css";

const EMPTY: FeatureCollection = { type: "FeatureCollection", features: [] };
const MAP_STYLE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [
    {
      id: "background",
      type: "background",
      paint: { "background-color": "#e8ece9" },
    },
  ],
};

interface MapViewProps {
  floor: string;
  floorMap: FeatureCollection;
  network: FeatureCollection;
  route: RouteResponse | null;
  start: Place | null;
  destination: Place | null;
  gates: Place[];
  exits: Place[];
  facilities: Facility[];
  mappings?: MappingSubmission[];
  onExitSelect?: (id: string) => void;
  onFacilitySelect?: (id: string) => void;
  onMapPick?: (lon: number, lat: number) => void;
  onReturnToStart?: () => void;
}

function updateSource(
  map: MapLibreMap,
  sourceId: string,
  data: FeatureCollection,
): void {
  (map.getSource(sourceId) as GeoJSONSource | undefined)?.setData(data);
}

function differentCoordinates(
  left: GeoJSON.Position,
  right: GeoJSON.Position,
): boolean {
  return left[0] !== right[0] || left[1] !== right[1];
}

export function sanitizeRouteForFloor(
  route: RouteResponse | null,
  floor: string,
  arrowsOnly = false,
): FeatureCollection {
  const features = [...(route?.route_by_floor[floor]?.features ?? [])]
    .sort(
      (left, right) =>
        Number(left.properties?.sequence ?? 0) -
        Number(right.properties?.sequence ?? 0),
    )
    .flatMap((feature) => {
      if (feature.geometry.type !== "LineString") return [];
      if (arrowsOnly && feature.properties?.is_transition === true) return [];
      const coordinates = feature.geometry.coordinates.filter(
        (coordinate, index, all) =>
          index === 0 || differentCoordinates(coordinate, all[index - 1]),
      );
      if (coordinates.length < 2) return [];
      return [
        {
          ...feature,
          geometry: { ...feature.geometry, coordinates },
        } as GeoJSON.Feature<GeoJSON.LineString, Record<string, unknown>>,
      ];
    });
  return { type: "FeatureCollection", features };
}

function transitionMarker(
  map: MapLibreMap,
  transition: FloorTransition,
): Marker {
  const element = document.createElement("div");
  element.className = styles.transitionMarker;
  const floorLevel = (floor: string) => {
    const basement = floor.match(/^B(\d+)$/i);
    if (basement) return -Number(basement[1]);
    const aboveGround = floor.match(/^(\d+)F$/i);
    return aboveGround ? Number(aboveGround[1]) : 0;
  };
  const direction =
    floorLevel(transition.to_floor) > floorLevel(transition.from_floor)
      ? "上へ"
      : "下へ";
  element.textContent = `${transition.label} ${direction} ${transition.to_floor}`;
  element.setAttribute("aria-label", element.textContent);
  return new maplibregl.Marker({ element, anchor: "bottom" })
    .setLngLat(transition.coordinate as [number, number])
    .addTo(map);
}

function pointCollection(
  floor: string,
  gates: Place[],
  exits: Place[],
  facilities: Facility[],
  mappings: MappingSubmission[],
): FeatureCollection {
  const features: GeoJSON.Feature<GeoJSON.Point, Record<string, unknown>>[] = [];
  for (const place of [...gates, ...exits].filter((item) => item.floor === floor)) {
    features.push({
      type: "Feature",
      properties: {
        id: place.id,
        kind: place.type,
        label: place.type === "exit" ? (place.exit_number ?? place.name) : place.name,
        symbol: place.type === "exit" ? "出" : "改",
      },
      geometry: { type: "Point", coordinates: [place.lon, place.lat] },
    });
  }
  for (const facility of facilities.filter((item) => item.floor === floor)) {
    const meta = FACILITY_META[facility.category];
    features.push({
      type: "Feature",
      properties: {
        id: facility.id,
        kind: "facility",
        category: facility.category,
        label: facility.name,
        symbol: meta.symbol,
        color: meta.color,
      },
      geometry: { type: "Point", coordinates: [facility.lon, facility.lat] },
    });
  }
  for (const mapping of mappings.filter((item) => item.floor === floor)) {
    features.push({
      type: "Feature",
      properties: {
        id: `mapping-${mapping.id}`,
        kind: "mapping",
        label: mapping.name,
        symbol: "投",
      },
      geometry: { type: "Point", coordinates: [mapping.lon, mapping.lat] },
    });
  }
  return { type: "FeatureCollection", features };
}

function selectionCollection(
  floor: string,
  start: Place | null,
  destination: Place | null,
): FeatureCollection {
  const features: GeoJSON.Feature<GeoJSON.Point, Record<string, unknown>>[] = [];
  if (start?.floor === floor) {
    features.push({
      type: "Feature",
      properties: { kind: "start", label: "出発" },
      geometry: { type: "Point", coordinates: [start.lon, start.lat] },
    });
  }
  if (destination?.floor === floor) {
    features.push({
      type: "Feature",
      properties: { kind: "destination", label: "目的地" },
      geometry: {
        type: "Point",
        coordinates: [destination.lon, destination.lat],
      },
    });
  }
  return { type: "FeatureCollection", features };
}

function routeCoordinates(
  route: RouteResponse | null,
  floor: string,
): [number, number][] {
  const result: [number, number][] = [];
  for (const feature of sanitizeRouteForFloor(route, floor).features) {
    if (feature.geometry.type !== "LineString") continue;
    for (const coordinate of feature.geometry.coordinates) {
      result.push(coordinate as [number, number]);
    }
  }
  return result;
}

export function MapView({
  floor,
  floorMap,
  network,
  route,
  start,
  destination,
  gates,
  exits,
  facilities,
  mappings = [],
  onExitSelect,
  onFacilitySelect,
  onMapPick,
  onReturnToStart,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markersRef = useRef<Marker[]>([]);
  const callbacksRef = useRef({
    onExitSelect,
    onFacilitySelect,
    onMapPick,
  });
  const lastFitRef = useRef("");

  useEffect(() => {
    callbacksRef.current = { onExitSelect, onFacilitySelect, onMapPick };
  }, [onExitSelect, onFacilitySelect, onMapPick]);

  useEffect(() => {
    if (containerRef.current === null || mapRef.current !== null) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLE,
      center: [139.7006, 35.691],
      zoom: 16.8,
      minZoom: 14,
      maxZoom: 21,
      attributionControl: false,
      localIdeographFontFamily:
        '"Noto Sans JP", "Yu Gothic UI", "Hiragino Kaku Gothic ProN", sans-serif',
    });
    map.addControl(
      new maplibregl.NavigationControl({
        showCompass: true,
        showZoom: true,
        visualizePitch: true,
      }),
      "top-right",
    );
    map.addControl(
      new maplibregl.AttributionControl({
        compact: true,
        customAttribution:
          '<a href="https://catalog.data.metro.tokyo.lg.jp/dataset/t000008d0000000037" target="_blank" rel="noreferrer">東京都都市整備局オープンデータを加工</a>',
      }),
    );
    map.on("load", () => {
      map.addSource("floor-map", { type: "geojson", data: EMPTY });
      map.addLayer({
        id: "floor-fill",
        type: "fill",
        source: "floor-map",
        paint: {
          "fill-color": [
            "match",
            ["get", "facility"],
            "elevator",
            "#b9e3d3",
            "escalator",
            "#f6d18b",
            "stairs",
            "#d5d7d4",
            "ramp",
            "#c7dced",
            "#fffdf8",
          ],
          "fill-opacity": 0.96,
          "fill-outline-color": "#adb7b3",
        },
      });
      map.addSource("network", { type: "geojson", data: EMPTY });
      map.addLayer({
        id: "network",
        type: "line",
        source: "network",
        filter: ["==", ["get", "is_vertical"], false],
        paint: {
          "line-color": "#7a8581",
          "line-width": ["interpolate", ["linear"], ["zoom"], 15, 0.7, 19, 2],
          "line-opacity": 0.32,
        },
      });
      map.addSource("route", { type: "geojson", data: EMPTY });
      map.addLayer({
        id: "route-casing",
        type: "line",
        source: "route",
        paint: {
          "line-color": "#ffffff",
          "line-width": ["interpolate", ["linear"], ["zoom"], 15, 9, 19, 14],
        },
      });
      map.addLayer({
        id: "route-line",
        type: "line",
        source: "route",
        paint: {
          "line-color": "#0072B2",
          "line-width": ["interpolate", ["linear"], ["zoom"], 15, 5, 19, 8],
        },
      });
      map.addSource("route-arrows", { type: "geojson", data: EMPTY });
      map.addLayer({
        id: "route-arrows",
        type: "symbol",
        source: "route-arrows",
        layout: {
          "symbol-placement": "line",
          "symbol-spacing": ["interpolate", ["linear"], ["zoom"], 15, 72, 20, 48],
          "text-field": "▶",
          "text-size": ["interpolate", ["linear"], ["zoom"], 15, 16, 20, 22],
          "text-rotation-alignment": "map",
          "text-pitch-alignment": "map",
          "text-keep-upright": false,
          "text-allow-overlap": true,
        },
        paint: {
          "text-color": "#ffffff",
          "text-halo-color": "#005F91",
          "text-halo-width": 2,
        },
      });
      map.addSource("points", { type: "geojson", data: EMPTY });
      map.addLayer({
        id: "facility-points",
        type: "circle",
        source: "points",
        filter: ["==", ["get", "kind"], "facility"],
        paint: {
          "circle-color": ["coalesce", ["get", "color"], "#777777"],
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 15, 5, 19, 8],
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 2,
        },
      });
      map.addLayer({
        id: "place-points",
        type: "circle",
        source: "points",
        filter: ["in", ["get", "kind"], ["literal", ["gate", "exit", "mapping"]]],
        paint: {
          "circle-color": [
            "match",
            ["get", "kind"],
            "gate",
            "#252A34",
            "exit",
            "#E69F00",
            "#CC79A7",
          ],
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 15, 7, 19, 11],
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 2,
        },
      });
      map.addLayer({
        id: "point-symbols",
        type: "symbol",
        source: "points",
        layout: {
          "text-field": ["get", "symbol"],
          "text-size": ["interpolate", ["linear"], ["zoom"], 15, 9, 19, 12],
          "text-font": ["Open Sans Bold"],
          "text-allow-overlap": true,
        },
        paint: { "text-color": "#ffffff" },
      });
      map.addLayer({
        id: "point-labels",
        type: "symbol",
        source: "points",
        minzoom: 17.2,
        layout: {
          "text-field": ["get", "label"],
          "text-size": 12,
          "text-offset": [0, 1.5],
          "text-anchor": "top",
          "text-optional": true,
        },
        paint: {
          "text-color": "#17211f",
          "text-halo-color": "#ffffff",
          "text-halo-width": 2,
        },
      });
      map.addSource("selection", { type: "geojson", data: EMPTY });
      map.addLayer({
        id: "selection-halo",
        type: "circle",
        source: "selection",
        paint: {
          "circle-color": [
            "match",
            ["get", "kind"],
            "start",
            "#009E73",
            "#D55E00",
          ],
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 15, 11, 19, 17],
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 4,
        },
      });
      map.addLayer({
        id: "selection-symbol",
        type: "symbol",
        source: "selection",
        layout: {
          "text-field": [
            "match",
            ["get", "kind"],
            "start",
            "S",
            "G",
          ],
          "text-size": 13,
          "text-allow-overlap": true,
        },
        paint: { "text-color": "#ffffff" },
      });
    });
    map.on("click", (event) => {
      const featuresAtPoint = map.queryRenderedFeatures(event.point, {
        layers: ["place-points", "facility-points"],
      });
      const selected = featuresAtPoint[0]?.properties as
        | { id?: string; kind?: string }
        | undefined;
      if (selected?.kind === "exit" && selected.id) {
        callbacksRef.current.onExitSelect?.(selected.id);
        return;
      }
      if (selected?.kind === "facility" && selected.id) {
        callbacksRef.current.onFacilitySelect?.(selected.id);
        return;
      }
      callbacksRef.current.onMapPick?.(event.lngLat.lng, event.lngLat.lat);
    });
    map.on("mousemove", (event) => {
      const interactive = map.queryRenderedFeatures(event.point, {
        layers: ["place-points", "facility-points"],
      });
      map.getCanvas().style.cursor = interactive.length > 0 ? "pointer" : "";
    });
    mapRef.current = map;
    return () => {
      markersRef.current.forEach((marker) => marker.remove());
      markersRef.current = [];
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const renderData = () => {
      updateSource(map, "floor-map", floorMap);
      updateSource(map, "network", network);
      updateSource(map, "route", sanitizeRouteForFloor(route, floor));
      updateSource(map, "route-arrows", sanitizeRouteForFloor(route, floor, true));
      updateSource(
        map,
        "points",
        pointCollection(floor, gates, exits, facilities, mappings),
      );
      updateSource(map, "selection", selectionCollection(floor, start, destination));
      markersRef.current.forEach((marker) => marker.remove());
      markersRef.current = (route?.floor_transitions ?? [])
        .filter(
          (transition) =>
            transition.from_floor === floor || transition.to_floor === floor,
        )
        .map((transition) => transitionMarker(map, transition));

      const fitKey = `${route?.route_id ?? "none"}:${floor}`;
      if (route && fitKey !== lastFitRef.current) {
        lastFitRef.current = fitKey;
        const coordinates = routeCoordinates(route, floor);
        if (coordinates.length > 1) {
          const bounds = new maplibregl.LngLatBounds(coordinates[0], coordinates[0]);
          coordinates.slice(1).forEach((coordinate) => bounds.extend(coordinate));
          map.fitBounds(bounds, { padding: 72, maxZoom: 19.2, duration: 450 });
        }
      }
    };
    if (map.isStyleLoaded()) renderData();
    else map.once("load", renderData);
  }, [destination, exits, facilities, floor, floorMap, gates, mappings, network, route, start]);

  const fitRoute = () => {
    const map = mapRef.current;
    const coordinates = routeCoordinates(route, floor);
    if (!map || coordinates.length === 0) return;
    if (coordinates.length === 1) {
      map.easeTo({ center: coordinates[0], zoom: 19 });
      return;
    }
    const bounds = new maplibregl.LngLatBounds(coordinates[0], coordinates[0]);
    coordinates.slice(1).forEach((coordinate) => bounds.extend(coordinate));
    map.fitBounds(bounds, { padding: 72, maxZoom: 19.2 });
  };

  const returnToStart = () => {
    onReturnToStart?.();
    if (start?.floor === floor) {
      mapRef.current?.easeTo({ center: [start.lon, start.lat], zoom: 19 });
    }
  };

  return (
    <>
      <div
        ref={containerRef}
        className={styles.map}
        role="region"
        aria-label={`${floor}の地下通路、地点、推奨経路の2D地図`}
      />
      <div className={styles.mapActions} aria-label="地図操作">
        <button type="button" onClick={fitRoute} disabled={!route}>
          ⛶ 経路全体
        </button>
        <button type="button" onClick={returnToStart} disabled={!start}>
          S 出発へ
        </button>
        <button type="button" onClick={() => mapRef.current?.resetNorth()}>
          ↑ 北を上へ
        </button>
      </div>
      <div className={styles.legend} aria-label="地図の凡例">
        <span><i className={styles.routeSwatch} />推奨経路・矢印</span>
        <span><i className={styles.startSwatch} />出発 S</span>
        <span><i className={styles.goalSwatch} />目的地 G</span>
        <span><i className={styles.gateSwatch} />改札</span>
        <span><i className={styles.exitSwatch} />出口</span>
        <span><i className={styles.facilitySwatch} />店舗・施設</span>
        <span><i className={styles.transitionSwatch} />階層移動</span>
      </div>
    </>
  );
}
