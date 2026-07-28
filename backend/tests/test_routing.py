from __future__ import annotations

from pathlib import Path
from typing import Any

import networkx as nx
import pytest

from app.core.config import Settings
from app.core.errors import RouteNotFoundError
from app.repositories.public_data import PublicDataRepository
from app.schemas.api import Place
from app.services.routing import calculate_route


def node_feature(node_id: str, floor: str, lon: float, lat: float) -> dict[str, Any]:
    return {
        "type": "Feature",
        "properties": {"id": node_id, "floor": floor},
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
    }


def repository_with_graph(graph: nx.MultiDiGraph, places: list[Place]) -> PublicDataRepository:
    return PublicDataRepository(
        graph=graph,
        nodes_geojson={"type": "FeatureCollection", "features": []},
        links_geojson={"type": "FeatureCollection", "features": []},
        floor_map_geojson={"type": "FeatureCollection", "features": []},
        places=places,
        facilities=[],
        landmarks=[],
        manifest={
            "data_mode": "fixture",
            "title": "テスト専用フィクスチャ",
            "provider": "tests",
            "license": "test-only",
            "catalog_url": "https://example.invalid/test-fixture",
            "warnings": [],
        },
        directory=Path("test-fixture"),
    )


def add_edge(
    graph: nx.MultiDiGraph,
    source: str,
    target: str,
    length: float,
    link_type: str = "corridor",
    *,
    vertical: bool = False,
) -> None:
    graph.add_edge(
        source,
        target,
        id=f"{source}-{target}-{link_type}",
        length_m=length,
        link_type=link_type,
        is_vertical=vertical,
        from_floor=graph.nodes[source]["floor"],
        to_floor=graph.nodes[target]["floor"],
        geometry={
            "type": "LineString",
            "coordinates": [
                [graph.nodes[source]["lon"], graph.nodes[source]["lat"]],
                [graph.nodes[target]["lon"], graph.nodes[target]["lat"]],
            ],
        },
    )


def places() -> tuple[Place, Place]:
    return (
        Place(
            id="gate-a",
            type="gate",
            name="テスト改札",
            operator="tests",
            direction="テスト",
            floor="B1",
            lon=139.7,
            lat=35.69,
            node_id="a",
            snap_distance_m=0,
        ),
        Place(
            id="exit-c",
            type="exit",
            name="テスト出口",
            operator="tests",
            direction="テスト",
            floor="1F",
            lon=139.7002,
            lat=35.6902,
            node_id="c",
            snap_distance_m=0,
        ),
    )


def settings() -> Settings:
    return Settings(data_dir=Path("test-fixture"), cors_origins=())


def test_distance_weight_selects_shortest_available_route() -> None:
    graph = nx.MultiDiGraph()
    graph.add_node("a", lon=139.7, lat=35.69, floor="B1")
    graph.add_node("b", lon=139.7001, lat=35.6901, floor="B1")
    graph.add_node("c", lon=139.7002, lat=35.6902, floor="1F")
    add_edge(graph, "a", "c", 5, "stairs", vertical=True)
    add_edge(graph, "a", "b", 8)
    add_edge(graph, "b", "c", 8, "elevator", vertical=True)
    start, destination = places()
    repository = repository_with_graph(graph, [start, destination])

    shortest = calculate_route(
        repository, settings(), start, destination, avoid_stairs=False
    )
    accessible = calculate_route(
        repository, settings(), start, destination, avoid_stairs=True
    )

    assert shortest.distance_meters == 5
    assert shortest.floor_transitions[0].type == "stairs"
    assert accessible.distance_meters == 16
    assert accessible.floor_transitions[0].type == "elevator"


def test_disconnected_nodes_never_return_fabricated_route() -> None:
    graph = nx.MultiDiGraph()
    graph.add_node("a", lon=139.7, lat=35.69, floor="B1")
    graph.add_node("c", lon=139.7002, lat=35.6902, floor="1F")
    start, destination = places()
    repository = repository_with_graph(graph, [start, destination])

    with pytest.raises(RouteNotFoundError, match="到達できる経路がありません"):
        calculate_route(
            repository, settings(), start, destination, avoid_stairs=False
        )


def test_one_way_edge_is_not_treated_as_bidirectional() -> None:
    graph = nx.MultiDiGraph()
    graph.add_node("a", lon=139.7, lat=35.69, floor="B1")
    graph.add_node("c", lon=139.7002, lat=35.6902, floor="1F")
    add_edge(graph, "a", "c", 12, "elevator", vertical=True)
    start, destination = places()
    reverse_start = destination.model_copy(
        update={"id": "gate-c", "type": "gate", "node_id": "c"}
    )
    reverse_destination = start.model_copy(
        update={"id": "exit-a", "type": "exit", "node_id": "a"}
    )
    repository = repository_with_graph(graph, [reverse_start, reverse_destination])

    with pytest.raises(RouteNotFoundError):
        calculate_route(
            repository,
            settings(),
            reverse_start,
            reverse_destination,
            avoid_stairs=False,
        )


def test_route_features_keep_start_to_destination_sequence_for_arrows() -> None:
    graph = nx.MultiDiGraph()
    graph.add_node("a", lon=139.7, lat=35.69, floor="B1")
    graph.add_node("b", lon=139.7001, lat=35.6901, floor="B1")
    graph.add_node("c", lon=139.7002, lat=35.6902, floor="1F")
    add_edge(graph, "a", "b", 18)
    add_edge(graph, "b", "c", 6, "elevator", vertical=True)
    start, destination = places()
    repository = repository_with_graph(graph, [start, destination])

    route = calculate_route(
        repository, settings(), start, destination, avoid_stairs=False
    )
    features = route.route_by_floor["B1"].features

    assert [feature["properties"]["sequence"] for feature in features] == [0, 1]
    assert features[0]["geometry"]["coordinates"][0] == [139.7, 35.69]
    assert features[0]["geometry"]["coordinates"][-1] == [139.7001, 35.6901]


def test_long_planar_segment_gets_conservative_compass_instruction() -> None:
    graph = nx.MultiDiGraph()
    graph.add_node("a", lon=139.7, lat=35.69, floor="B1")
    graph.add_node("b", lon=139.7003, lat=35.6903, floor="B1")
    graph.add_node("c", lon=139.7004, lat=35.6904, floor="1F")
    add_edge(graph, "a", "b", 42)
    add_edge(graph, "b", "c", 6, "elevator", vertical=True)
    start, destination = places()
    repository = repository_with_graph(graph, [start, destination])

    route = calculate_route(
        repository, settings(), start, destination, avoid_stairs=False
    )

    assert any(
        "北東へ約42メートル進みます" in instruction.text
        for instruction in route.instructions
    )
