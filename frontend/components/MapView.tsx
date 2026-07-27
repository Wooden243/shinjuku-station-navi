"use client";

import { useEffect, useRef } from "react";
import maplibregl, {
  type GeoJSONSource,
  type Map as MapLibreMap,
  type Marker,
  type StyleSpecification,
} from "maplibre-gl";

import type {
  FeatureCollection,
  FloorTransition,
  Place,
  RouteResponse,
} from "@/lib/types";

import styles from "./MapView.module.css";

const EMPTY: FeatureCollection = {
  type: "FeatureCollection",
  features: [],
};

const MAP_STYLE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [
    {
      id: "background",
      type: "background",
      paint: { "background-color": "#e9e9e3" },
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
}

function updateSource(
  map: MapLibreMap,
  sourceId: string,
  data: FeatureCollection,
): void {
  (map.getSource(sourceId) as GeoJSONSource | undefined)?.setData(data);
}

function placeMarker(
  map: MapLibreMap,
  place: Place,
  kind: "start" | "destination",
): Marker {
  const element = document.createElement("div");
  element.className =
    kind === "destination"
      ? `${styles.placeMarker} ${styles.destinationMarker}`
      : styles.placeMarker;
  element.textContent = kind === "start" ? "出" : "着";
  element.title = place.name;
  element.setAttribute("aria-label", `${kind === "start" ? "出発" : "到着"}: ${place.name}`);
  return new maplibregl.Marker({ element, anchor: "center" })
    .setLngLat([place.lon, place.lat])
    .addTo(map);
}

function transitionMarker(
  map: MapLibreMap,
  transition: FloorTransition,
): Marker {
  const element = document.createElement("div");
  element.className = styles.transitionMarker;
  element.textContent = `${transition.label} ${transition.from_floor}→${transition.to_floor}`;
  element.setAttribute("aria-label", element.textContent);
  return new maplibregl.Marker({ element, anchor: "bottom" })
    .setLngLat(transition.coordinate as [number, number])
    .addTo(map);
}

function routeCoordinates(
  route: RouteResponse | null,
  floor: string,
): [number, number][] {
  const result: [number, number][] = [];
  for (const feature of route?.route_by_floor[floor]?.features ?? []) {
    if (feature.geometry.type !== "LineString") {
      continue;
    }
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
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markersRef = useRef<Marker[]>([]);

  useEffect(() => {
    if (containerRef.current === null || mapRef.current !== null) {
      return;
    }
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLE,
      center: [139.7006, 35.691],
      zoom: 16.9,
      minZoom: 14,
      maxZoom: 21,
      attributionControl: false,
    });
    map.addControl(
      new maplibregl.NavigationControl({ showCompass: false }),
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
            "#baddeb",
            "escalator",
            "#f3d5a8",
            "stairs",
            "#ded8cd",
            "#fbfaf6",
          ],
          "fill-opacity": 0.94,
          "fill-outline-color": "#bbb9b1",
        },
      });
      map.addSource("network", { type: "geojson", data: EMPTY });
      map.addLayer({
        id: "network",
        type: "line",
        source: "network",
        filter: ["==", ["get", "is_vertical"], false],
        paint: {
          "line-color": "#657576",
          "line-width": ["interpolate", ["linear"], ["zoom"], 15, 1, 19, 3],
          "line-opacity": 0.75,
        },
      });
      map.addSource("route", { type: "geojson", data: EMPTY });
      map.addLayer({
        id: "route-casing",
        type: "line",
        source: "route",
        paint: {
          "line-color": "#fff",
          "line-width": ["interpolate", ["linear"], ["zoom"], 15, 7, 19, 12],
        },
      });
      map.addLayer({
        id: "route",
        type: "line",
        source: "route",
        paint: {
          "line-color": "#d6342b",
          "line-width": ["interpolate", ["linear"], ["zoom"], 15, 4, 19, 7],
        },
      });
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
    if (map === null) {
      return;
    }

    const renderData = () => {
      updateSource(map, "floor-map", floorMap);
      updateSource(map, "network", network);
      updateSource(map, "route", route?.route_by_floor[floor] ?? EMPTY);

      markersRef.current.forEach((marker) => marker.remove());
      const markers: Marker[] = [];
      if (start?.floor === floor) {
        markers.push(placeMarker(map, start, "start"));
      }
      if (destination?.floor === floor) {
        markers.push(placeMarker(map, destination, "destination"));
      }
      for (const transition of route?.floor_transitions ?? []) {
        if (
          transition.from_floor === floor ||
          transition.to_floor === floor
        ) {
          markers.push(transitionMarker(map, transition));
        }
      }
      markersRef.current = markers;

      const coordinates = routeCoordinates(route, floor);
      if (coordinates.length > 1) {
        const bounds = new maplibregl.LngLatBounds(
          coordinates[0],
          coordinates[0],
        );
        coordinates.slice(1).forEach((coordinate) => bounds.extend(coordinate));
        map.fitBounds(bounds, {
          padding: 72,
          maxZoom: 19.2,
          duration: 450,
        });
      }
    };

    if (map.isStyleLoaded()) {
      renderData();
    } else {
      map.once("load", renderData);
    }
  }, [destination, floor, floorMap, network, route, start]);

  return (
    <>
      <div
        ref={containerRef}
        className={styles.map}
        role="region"
        aria-label={`${floor}の地下通路と推奨経路の2D地図`}
      />
      <div className={styles.legend} aria-label="地図の凡例">
        <span>
          <i className={styles.routeSwatch} aria-hidden="true" />
          推奨経路
        </span>
        <span>
          <i className={styles.passageSwatch} aria-hidden="true" />
          通路
        </span>
      </div>
    </>
  );
}
