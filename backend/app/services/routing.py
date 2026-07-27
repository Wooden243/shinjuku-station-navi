from __future__ import annotations

import hashlib
from collections import defaultdict
from itertools import pairwise
from typing import Any

import networkx as nx

from app.core.config import Settings
from app.core.errors import RouteNotFoundError
from app.repositories.public_data import PublicDataRepository
from app.schemas.api import (
    DataSource,
    FeatureCollection,
    FloorTransition,
    Instruction,
    Landmark,
    Place,
    RouteResponse,
)

STAIR_TYPES = {"stairs", "stair"}
TRANSITION_LABELS = {
    "stairs": "階段",
    "stair": "階段",
    "escalator": "エスカレーター",
    "elevator": "エレベーター",
    "movingwalkway": "動く歩道",
    "ramp": "スロープ",
    "vertical": "階層移動設備（種別不明）",
}


def _eligible_edges(
    edges: dict[int, dict[str, Any]],
    *,
    avoid_stairs: bool,
) -> list[dict[str, Any]]:
    return [
        attrs
        for attrs in edges.values()
        if not (
            avoid_stairs
            and str(attrs.get("link_type", "")).lower() in STAIR_TYPES
        )
    ]


def _weight(
    _source: str,
    _target: str,
    edges: dict[int, dict[str, Any]],
    *,
    avoid_stairs: bool,
) -> float:
    candidates = _eligible_edges(edges, avoid_stairs=avoid_stairs)
    if not candidates:
        return float("inf")
    return min(float(edge["length_m"]) for edge in candidates)


def _best_edge(
    graph: nx.MultiDiGraph,
    source: str,
    target: str,
    *,
    avoid_stairs: bool,
) -> dict[str, Any]:
    candidates = _eligible_edges(graph[source][target], avoid_stairs=avoid_stairs)
    if not candidates:
        raise RouteNotFoundError("指定条件で利用できる通路がありません。")
    return min(candidates, key=lambda edge: float(edge["length_m"]))


def _floor_sequence(graph: nx.MultiDiGraph, path: list[str]) -> list[str]:
    floors: list[str] = []
    for node_id in path:
        floor = str(graph.nodes[node_id]["floor"])
        if not floors or floors[-1] != floor:
            floors.append(floor)
    return floors


def _transition(
    graph: nx.MultiDiGraph,
    source: str,
    target: str,
    edge: dict[str, Any],
) -> FloorTransition:
    source_floor = str(graph.nodes[source]["floor"])
    target_floor = str(graph.nodes[target]["floor"])
    link_type = str(edge["link_type"])
    coordinate = [
        float(graph.nodes[target]["lon"]),
        float(graph.nodes[target]["lat"]),
    ]
    return FloorTransition(
        from_floor=source_floor,
        to_floor=target_floor,
        type=link_type,
        label=TRANSITION_LABELS.get(link_type, "階層移動設備（種別不明）"),
        coordinate=coordinate,
    )


def _instructions(
    graph: nx.MultiDiGraph,
    path: list[str],
    edges: list[dict[str, Any]],
    start: Place,
    destination: Place,
) -> tuple[list[Instruction], list[FloorTransition]]:
    instructions = [
        Instruction(
            order=1,
            floor=start.floor,
            text=f"{start.name}を出発し、地図上の推奨経路に沿って進みます。",
            coordinate=[start.lon, start.lat],
        )
    ]
    transitions: list[FloorTransition] = []
    order = 2
    accumulated = 0.0
    segment_floor = str(graph.nodes[path[0]]["floor"])
    neighbor_counts = {
        node_id: len(set(graph.predecessors(node_id)) | set(graph.successors(node_id)))
        for node_id in path
    }

    for index, edge in enumerate(edges):
        source, target = path[index], path[index + 1]
        source_floor = str(graph.nodes[source]["floor"])
        target_floor = str(graph.nodes[target]["floor"])
        link_type = str(edge["link_type"])
        length = float(edge["length_m"])
        is_transition = source_floor != target_floor or bool(edge["is_vertical"])

        if is_transition:
            if accumulated > 0:
                instructions.append(
                    Instruction(
                        order=order,
                        floor=segment_floor,
                        text=f"{segment_floor}を約{round(accumulated):.0f}メートル進みます。",
                        distance_meters=round(accumulated, 1),
                    )
                )
                order += 1
                accumulated = 0.0
            transition = _transition(graph, source, target, edge)
            transitions.append(transition)
            instructions.append(
                Instruction(
                    order=order,
                    floor=source_floor,
                    text=(
                        f"{transition.label}で{source_floor}から"
                        f"{target_floor}へ移動します。"
                    ),
                    distance_meters=round(length, 1),
                    transition_type=link_type,
                    coordinate=transition.coordinate,
                )
            )
            order += 1
            segment_floor = target_floor
            continue

        accumulated += length
        if (
            accumulated >= 25
            and neighbor_counts[target] >= 3
            and index < len(edges) - 1
        ):
            instructions.append(
                Instruction(
                    order=order,
                    floor=segment_floor,
                    text=(
                        f"{segment_floor}を約{round(accumulated):.0f}メートル進み、"
                        "分岐では地図上の次の通路へ進みます。"
                    ),
                    distance_meters=round(accumulated, 1),
                    coordinate=[
                        float(graph.nodes[target]["lon"]),
                        float(graph.nodes[target]["lat"]),
                    ],
                )
            )
            order += 1
            accumulated = 0.0

    if accumulated > 0:
        instructions.append(
            Instruction(
                order=order,
                floor=segment_floor,
                text=f"{segment_floor}を約{round(accumulated):.0f}メートル進みます。",
                distance_meters=round(accumulated, 1),
            )
        )
        order += 1
    instructions.append(
        Instruction(
            order=order,
            floor=destination.floor,
            text=(
                f"{destination.name}に到着します。現地の案内表示と通行状況を確認してください。"
            ),
            coordinate=[destination.lon, destination.lat],
        )
    )
    return instructions, transitions


def calculate_route(
    repository: PublicDataRepository,
    settings: Settings,
    start: Place,
    destination: Place,
    *,
    avoid_stairs: bool,
) -> RouteResponse:
    graph = repository.graph
    try:
        path = nx.shortest_path(
            graph,
            start.node_id,
            destination.node_id,
            weight=lambda source, target, edges: _weight(
                source,
                target,
                edges,
                avoid_stairs=avoid_stairs,
            ),
        )
    except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
        raise RouteNotFoundError(
            "選択した改札と出口の間に、指定条件で到達できる経路がありません。"
        ) from exc

    edges = [
        _best_edge(graph, source, target, avoid_stairs=avoid_stairs)
        for source, target in pairwise(path)
    ]
    if not edges and start.node_id != destination.node_id:
        raise RouteNotFoundError("経路を構成する通路がありません。")

    distance = sum(float(edge["length_m"]) for edge in edges)
    route_features: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, edge in enumerate(edges):
        source, target = path[index], path[index + 1]
        source_floor = str(graph.nodes[source]["floor"])
        target_floor = str(graph.nodes[target]["floor"])
        floors = [source_floor] if source_floor == target_floor else [source_floor, target_floor]
        for floor in floors:
            route_features[floor].append(
                {
                    "type": "Feature",
                    "properties": {
                        "id": edge["id"],
                        "floor": floor,
                        "link_type": edge["link_type"],
                        "is_transition": source_floor != target_floor
                        or bool(edge["is_vertical"]),
                    },
                    "geometry": edge["geometry"],
                }
            )

    instructions, transitions = _instructions(
        graph, path, edges, start, destination
    )
    landmarks_by_node = repository.landmarks_by_node
    route_landmarks: list[Landmark] = []
    seen_landmarks: set[str] = set()
    for node_id in path:
        for landmark in landmarks_by_node.get(node_id, []):
            if landmark.id not in seen_landmarks:
                route_landmarks.append(landmark)
                seen_landmarks.add(landmark.id)

    warnings = [
        "この経路は公開データに基づく参考情報です。現地の案内表示と係員の指示を優先してください。",
        "公開データは調査時点の情報であり、工事・閉鎖・営業時間・現況の変更を反映していない場合があります。",
    ]
    if not start.verified_on_site or not destination.verified_on_site:
        warnings.append("選択地点は本アプリ開発者による現地確認が完了していません。")
    if (
        start.snap_distance_m > settings.snap_warning_meters
        or destination.snap_distance_m > settings.snap_warning_meters
    ):
        warnings.append(
            "改札または出口からNavネットワークへのスナップ距離が15メートルを超えています。"
        )
    conversion_warnings = len(repository.manifest.get("warnings", []))
    if conversion_warnings:
        warnings.append(
            f"データ正規化時に{conversion_warnings}件の警告があります。詳細はmanifestを確認してください。"
        )

    route_key = f"{start.id}|{destination.id}|{avoid_stairs}|{'/'.join(path)}"
    route_id = hashlib.sha256(route_key.encode("utf-8")).hexdigest()[:16]
    manifest = repository.manifest
    return RouteResponse(
        route_id=route_id,
        start_gate=start,
        destination_exit=destination,
        distance_meters=round(distance, 1),
        estimated_walking_minutes=round(
            distance / settings.walking_speed_m_per_minute, 1
        ),
        floors=_floor_sequence(graph, path),
        floor_transitions=transitions,
        route_by_floor={
            floor: FeatureCollection(features=features)
            for floor, features in route_features.items()
        },
        instructions=instructions,
        landmarks=route_landmarks,
        warnings=warnings,
        data_source=DataSource(
            data_mode=manifest["data_mode"],
            title=str(manifest["title"]),
            provider=str(manifest["provider"]),
            license=str(manifest["license"]),
            catalog_url=str(manifest["catalog_url"]),
            specification_revision=manifest.get("specification_revision"),
            generated_at=manifest.get("generated_at"),
            source_map_version=manifest.get("source_map_version"),
        ),
    )
