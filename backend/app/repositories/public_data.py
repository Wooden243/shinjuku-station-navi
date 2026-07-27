from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import networkx as nx

from app.core.errors import DataLoadError
from app.schemas.api import Landmark, Place

REQUIRED_FILES = (
    "nodes.geojson",
    "links.geojson",
    "places.json",
    "landmarks.json",
    "floor_map.geojson",
    "manifest.json",
)


def floor_sort_key(floor: str) -> tuple[int, float, str]:
    if floor.startswith("B") and floor[1:].isdigit():
        return (0, -float(floor[1:]), floor)
    if floor == "MB2":
        return (0, -2.5, floor)
    if floor == "M1":
        return (0, -0.5, floor)
    if floor.endswith("F") and floor[:-1].isdigit():
        return (1, float(floor[:-1]), floor)
    return (2, 0.0, floor)


def _read_json(path: Path) -> Any:
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataLoadError(f"データファイルを読み込めません: {path.name}") from exc


@dataclass
class PublicDataRepository:
    graph: nx.MultiDiGraph
    nodes_geojson: dict[str, Any]
    links_geojson: dict[str, Any]
    floor_map_geojson: dict[str, Any]
    places: list[Place]
    landmarks: list[Landmark]
    manifest: dict[str, Any]
    directory: Path

    @property
    def places_by_id(self) -> dict[str, Place]:
        return {place.id: place for place in self.places}

    @property
    def landmarks_by_node(self) -> dict[str, list[Landmark]]:
        grouped: dict[str, list[Landmark]] = {}
        for landmark in self.landmarks:
            grouped.setdefault(landmark.node_id, []).append(landmark)
        return grouped

    @property
    def floors(self) -> list[str]:
        return sorted(
            {str(attrs["floor"]) for _, attrs in self.graph.nodes(data=True)},
            key=floor_sort_key,
        )

    def network_for_floor(self, floor: str) -> dict[str, Any]:
        features = [
            feature
            for feature in self.links_geojson["features"]
            if floor
            in {
                str(feature["properties"]["from_floor"]),
                str(feature["properties"]["to_floor"]),
            }
        ]
        return {"type": "FeatureCollection", "features": features}

    def floor_map_for_floor(self, floor: str) -> dict[str, Any]:
        features = [
            feature
            for feature in self.floor_map_geojson["features"]
            if str(feature["properties"]["floor"]) == floor
        ]
        return {"type": "FeatureCollection", "features": features}


def load_public_data(directory: Path) -> PublicDataRepository:
    missing = [name for name in REQUIRED_FILES if not (directory / name).is_file()]
    if missing:
        raise DataLoadError(
            f"正規化済み公開データが不足しています: {', '.join(sorted(missing))}"
        )
    manifest = _read_json(directory / "manifest.json")
    data_mode = str(manifest.get("data_mode", ""))
    allow_fixture = os.getenv("SHINJUKU_ALLOW_FIXTURE_DATA", "").lower() == "true"
    if data_mode != "open-data" and not (data_mode == "fixture" and allow_fixture):
        raise DataLoadError(
            "公開データ以外のバンドルは本番モードでは読み込めません"
        )
    if manifest.get("crs") != "EPSG:4326":
        raise DataLoadError("API用データのCRSはEPSG:4326である必要があります")
    if manifest.get("distance_unit") != "meter":
        raise DataLoadError("リンク距離単位はmeterである必要があります")

    nodes = _read_json(directory / "nodes.geojson")
    links = _read_json(directory / "links.geojson")
    floor_map = _read_json(directory / "floor_map.geojson")
    places = [Place.model_validate(item) for item in _read_json(directory / "places.json")]
    landmarks = [
        Landmark.model_validate(item)
        for item in _read_json(directory / "landmarks.json")
    ]
    graph = nx.MultiDiGraph()

    for feature in nodes.get("features", []):
        props = feature.get("properties", {})
        floor = str(props.get("floor", ""))
        if not floor or floor == "UNKNOWN":
            raise DataLoadError("不明階層のNav Nodeは経路グラフへ読み込めません")
        coordinates = feature.get("geometry", {}).get("coordinates", [])
        if len(coordinates) < 2:
            raise DataLoadError("Nav NodeにEPSG:4326座標がありません")
        graph.add_node(
            str(props["id"]),
            lon=float(coordinates[0]),
            lat=float(coordinates[1]),
            floor=floor,
            facility=props.get("facility"),
        )

    for feature in links.get("features", []):
        props = feature.get("properties", {})
        source = str(props["source"])
        target = str(props["target"])
        if source not in graph or target not in graph:
            raise DataLoadError(f"Nav Link {props.get('id')} の端点が存在しません")
        length = float(props["length_m"])
        is_vertical = bool(props["is_vertical"])
        if length < 0 or (length == 0 and not is_vertical):
            raise DataLoadError(f"Nav Link {props.get('id')} の距離が不正です")
        direction = str(props["direction"])
        attrs = {
            "id": str(props["id"]),
            "length_m": length,
            "link_type": str(props["link_type"]),
            "is_vertical": is_vertical,
            "from_floor": str(props["from_floor"]),
            "to_floor": str(props["to_floor"]),
            "geometry": feature["geometry"],
        }
        if direction in {"forward", "both"}:
            graph.add_edge(source, target, **attrs)
        if direction in {"reverse", "both"}:
            reversed_geometry = {
                "type": "LineString",
                "coordinates": list(reversed(feature["geometry"]["coordinates"])),
            }
            graph.add_edge(
                target,
                source,
                **{
                    **attrs,
                    "from_floor": attrs["to_floor"],
                    "to_floor": attrs["from_floor"],
                    "geometry": reversed_geometry,
                },
            )
        if direction not in {"forward", "reverse", "both"}:
            raise DataLoadError(f"Nav Link {props.get('id')} の方向が不正です")

    for place in places:
        if place.node_id not in graph:
            raise DataLoadError(f"地点 {place.id} の接続先Nav Nodeが存在しません")

    return PublicDataRepository(
        graph=graph,
        nodes_geojson=nodes,
        links_geojson=links,
        floor_map_geojson=floor_map,
        places=places,
        landmarks=landmarks,
        manifest=manifest,
        directory=directory,
    )
