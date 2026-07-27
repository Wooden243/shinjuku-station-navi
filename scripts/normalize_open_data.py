from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
import zipfile
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import geopandas as gpd
from pyproj import Geod
from shapely.geometry import shape

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"
OVERRIDES_PATH = PROJECT_ROOT / "data" / "overrides" / "place_overrides.csv"
ZIP_PATH = RAW_DIR / "shisetsu_root.zip"
RAW_MANIFEST_PATH = RAW_DIR / "manifest.json"
GEOD = Geod(ellps="WGS84")
KNOWN_FACILITIES = {"stairs", "escalator", "elevator", "ramp", "movingwalkway", "step"}
VERTICAL_FACILITIES = {"stairs", "escalator", "elevator", "movingwalkway", "vertical"}
EXIT_NAME_PATTERN = re.compile(r"^[A-Z]{0,2}\d{1,2}[A-Z]?$|^[A-Z]$")


def zip_member(archive: zipfile.ZipFile, basename: str) -> str:
    matches = [name for name in archive.namelist() if name.endswith(f"/{basename}")]
    if len(matches) != 1:
        raise ValueError(f"ZIP member {basename!r} expected once, found {len(matches)}")
    return matches[0]


def read_zip_json(archive: zipfile.ZipFile, basename: str) -> dict[str, Any]:
    try:
        return json.loads(archive.read(zip_member(archive, basename)))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"ZIP member is not valid UTF-8 JSON: {basename}") from exc


def property_list(rows: Iterable[list[Any]]) -> dict[str, list[Any]]:
    result: dict[str, list[Any]] = defaultdict(list)
    for row in rows:
        if len(row) < 2:
            continue
        result[str(row[0])].append(row[1])
    return dict(result)


def normalize_floor(value: str) -> str:
    text = value.strip().upper()
    if text.endswith("F") and text[:-1]:
        text = text[:-1]
    if re.fullmatch(r"B\d+", text) or re.fullmatch(r"\d+F", text):
        return text
    if re.fullmatch(r"\d+", text):
        return f"{text}F"
    if text in {"M1", "MB2"}:
        return text
    raise ValueError(f"Unrecognized public level name: {value!r}")


def floor_sort_key(floor: str) -> tuple[int, float, str]:
    if floor.startswith("B") and floor[1:].isdigit():
        return (0, -float(floor[1:]), floor)
    if floor == "MB2":
        return (0, -2.5, floor)
    if floor == "M1":
        return (0, -0.5, floor)
    if floor.endswith("F") and floor[:-1].isdigit():
        return (1, float(floor[:-1]), floor)
    return (2, 0, floor)


def affine(x: float, y: float, values: list[float]) -> tuple[float, float]:
    if len(values) != 6:
        raise ValueError("Affine transform must contain six values")
    return (
        values[0] * x + values[2] * y + values[4],
        values[1] * x + values[3] * y + values[5],
    )


def geodesic_m(left: tuple[float, float], right: tuple[float, float]) -> float:
    _, _, distance = GEOD.inv(left[0], left[1], right[0], right[1])
    return float(distance)


def facility_type(feature: dict[str, Any] | None) -> str:
    if feature is None:
        return ""
    value = str(feature.get("properties", {}).get("facility", "")).lower().replace(" ", "")
    aliases = {
        "flooropening": "vertical",
        "movingwalkway": "movingwalkway",
        "step": "stairs",
    }
    return aliases.get(value, value)


def operator_from_public_name(name: str) -> str:
    rules = (
        ("丸の内線", "東京メトロ"),
        ("丸ノ内線", "東京メトロ"),
        ("都営", "東京都交通局"),
        ("大江戸線", "東京都交通局"),
        ("京王", "京王電鉄"),
        ("小田急", "小田急電鉄"),
        ("JR", "JR東日本"),
    )
    for prefix, operator in rules:
        if prefix in name:
            return operator
    return "公開データに事業者記載なし"


def load_level_geometries(
    archive: zipfile.ZipFile,
    level_names: dict[int, str],
) -> tuple[dict[int, dict[str, Any]], dict[str, list[dict[str, Any]]], list[str]]:
    by_id: dict[int, dict[str, Any]] = {}
    by_floor: dict[str, list[dict[str, Any]]] = defaultdict(list)
    warnings: list[str] = []
    for floor in level_names.values():
        public_name = f"{floor}F" if floor.startswith("B") else floor
        if floor in {"M1", "MB2"}:
            public_name = f"{floor}F"
        basename = f"geojson-level-geom-{public_name}.geojson"
        payload = read_zip_json(archive, basename)
        declared = normalize_floor(str(payload.get("properties", {}).get("name", public_name)))
        if declared != floor:
            raise ValueError(f"Level file mismatch: {basename} declares {declared}")
        for feature in payload.get("features", []):
            feature_id = int(feature["id"])
            if feature_id in by_id:
                warnings.append(f"Geometry ID {feature_id} appears on multiple levels")
            record = {**feature, "_floor": floor}
            by_id[feature_id] = record
            by_floor[floor].append(record)
    return by_id, dict(by_floor), warnings


def transform_nodes(
    nav: dict[str, Any],
    community_map: dict[str, Any],
    geometry_by_id: dict[int, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], list[str]]:
    nav_drawing = nav["d"][0]
    map_drawing = community_map["drawings"][0]
    nav_to_local = [float(value) for value in nav_drawing["t"]]
    local_to_wgs84 = [float(value) for value in map_drawing["ref_frame"]["transform"]]
    level_by_id = {
        int(level["id"]): normalize_floor(str(level["properties"]["name"]))
        for level in map_drawing["levels"]
    }
    features: list[dict[str, Any]] = []
    nodes: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []

    for item in nav.get("n", []):
        memberships = item.get("l", [])
        if len(memberships) != 1:
            warnings.append(
                f"Node {item.get('id')} has {len(memberships)} level memberships and was skipped"
            )
            continue
        membership = memberships[0]
        level_id = int(membership["lid"])
        if level_id not in level_by_id:
            warnings.append(f"Node {item.get('id')} references unknown level {level_id}")
            continue
        local_x, local_y = affine(float(item["mx"]), float(item["my"]), nav_to_local)
        lon, lat = affine(local_x, local_y, local_to_wgs84)
        if not (139.65 <= lon <= 139.75 and 35.65 <= lat <= 35.75):
            raise ValueError(f"Node {item['id']} transformed outside Shinjuku bounds: {lon}, {lat}")
        node_id = str(item["id"])
        geometry_id = int(membership.get("gid", 0))
        facility = facility_type(geometry_by_id.get(geometry_id))
        props = {
            "id": node_id,
            "floor": level_by_id[level_id],
            "level_id": level_id,
            "source_geometry_id": geometry_id or None,
            "facility": facility or None,
        }
        feature = {
            "type": "Feature",
            "properties": props,
            "geometry": {"type": "Point", "coordinates": [round(lon, 7), round(lat, 7)]},
        }
        features.append(feature)
        nodes[node_id] = {
            **props,
            "lon": lon,
            "lat": lat,
        }
    return {"type": "FeatureCollection", "features": features}, nodes, warnings


def infer_link_type(source: dict[str, Any], target: dict[str, Any], delta_z: int) -> str:
    facilities = {str(source.get("facility") or ""), str(target.get("facility") or "")}
    for preferred in ("elevator", "escalator", "stairs", "movingwalkway", "ramp"):
        if preferred in facilities:
            return preferred
    return "vertical" if delta_z else "corridor"


def transform_links(
    nav: dict[str, Any],
    nodes: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    features: list[dict[str, Any]] = []
    warnings: list[str] = []
    direction_map = {1: "forward", 2: "reverse", 3: "both"}
    for item in nav.get("l", []):
        source_id = str(item["n1"])
        target_id = str(item["n2"])
        if source_id not in nodes or target_id not in nodes:
            warnings.append(f"Link {item.get('id')} references a skipped node")
            continue
        if source_id == target_id:
            warnings.append(f"Link {item.get('id')} is a zero-distance self-loop and was skipped")
            continue
        source, target = nodes[source_id], nodes[target_id]
        delta_z = int(item.get("dz", 0))
        supplied = item.get("dm")
        try:
            length = float(supplied)
            if not math.isfinite(length) or length < 0:
                raise ValueError
            if length == 0 and (delta_z or source["floor"] != target["floor"]):
                length_source = "public-dm-zero-vertical"
                warnings.append(
                    f"Link {item.get('id')} is a public zero-meter vertical link; "
                    "no distance was fabricated"
                )
            elif length == 0:
                raise ValueError
            else:
                length_source = "public-dm"
        except (TypeError, ValueError):
            length = geodesic_m((source["lon"], source["lat"]), (target["lon"], target["lat"]))
            if length <= 0:
                warnings.append(
                    f"Link {item.get('id')} has no positive measurable length and was skipped"
                )
                continue
            length_source = "wgs84-geodesic-fallback"
            warnings.append(f"Link {item.get('id')} had invalid dm; geodesic length used")
        direction = direction_map.get(int(item.get("d", 0)))
        if direction is None:
            warnings.append(f"Link {item.get('id')} has unknown direction {item.get('d')}; skipped")
            continue
        link_type = infer_link_type(source, target, delta_z)
        if delta_z and link_type == "vertical":
            warnings.append(
                f"Link {item.get('id')} changes level but equipment type is not identified"
            )
        properties = {
            "id": str(item["id"]),
            "source": source_id,
            "target": target_id,
            "direction": direction,
            "length_m": round(length, 3),
            "length_source": length_source,
            "from_floor": source["floor"],
            "to_floor": target["floor"],
            "floor": source["floor"] if source["floor"] == target["floor"] else None,
            "delta_z": delta_z,
            "link_type": link_type,
            "is_vertical": source["floor"] != target["floor"] or delta_z != 0,
        }
        features.append(
            {
                "type": "Feature",
                "properties": properties,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [round(source["lon"], 7), round(source["lat"], 7)],
                        [round(target["lon"], 7), round(target["lat"], 7)],
                    ],
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}, warnings


def nearest_node(
    lon: float,
    lat: float,
    floor: str,
    nodes: dict[str, dict[str, Any]],
) -> tuple[str, float]:
    candidates = [node for node in nodes.values() if node["floor"] == floor]
    if not candidates:
        raise ValueError(f"No Nav Nodes exist on floor {floor}")
    distances = [
        (geodesic_m((lon, lat), (float(node["lon"]), float(node["lat"]))), str(node["id"]))
        for node in candidates
    ]
    distance, node_id = min(distances)
    return node_id, distance


def entity_name(entity: dict[str, Any]) -> str:
    return str(entity.get("properties", {}).get("name", "")).strip()


def build_places(
    entities: dict[int, dict[str, Any]],
    geometry_by_id: dict[int, dict[str, Any]],
    geometry_by_floor: dict[str, list[dict[str, Any]]],
    nodes: dict[str, dict[str, Any]],
    max_snap_m: float,
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    places: list[dict[str, Any]] = []
    warnings: list[str] = []
    report: dict[str, Any] = {"unclassified_gates": [], "skipped_exits": []}

    for feature in geometry_by_id.values():
        props = feature.get("properties", {})
        if props.get("barrier") != "gate":
            continue
        entity_ids = [int(value) for value in props.get("entities", [])]
        entity = next((entities[value] for value in entity_ids if value in entities), None)
        name = entity_name(entity) if entity else ""
        if not name:
            report["unclassified_gates"].append(feature["id"])
            continue
        location = feature.get("location")
        if not location:
            warnings.append(f"Gate geometry {feature['id']} has no location")
            continue
        lon, lat = [float(value) for value in location["coordinates"][:2]]
        floor = str(feature["_floor"])
        node_id, snap_distance = nearest_node(lon, lat, floor, nodes)
        if snap_distance > max_snap_m:
            warnings.append(
                f"Gate {name} skipped: snap distance {snap_distance:.1f}m exceeds {max_snap_m:.1f}m"
            )
            continue
        source_entity_id = int(entity["id"]) if entity else None
        places.append(
            {
                "id": f"gate-{source_entity_id or feature['id']}",
                "type": "gate",
                "name": name,
                "operator": operator_from_public_name(name),
                "direction": name,
                "floor": floor,
                "lon": round(lon, 7),
                "lat": round(lat, 7),
                "node_id": node_id,
                "snap_distance_m": round(snap_distance, 2),
                "source_entity_id": source_entity_id,
                "source_geometry_id": int(feature["id"]),
                "verified_on_site": False,
            }
        )

    exit_by_entity: dict[int, dict[str, Any]] = {}
    for feature in geometry_by_floor.get("1F", []):
        props = feature.get("properties", {})
        if props.get("marker") != "entrance":
            continue
        entity_ids = [int(value) for value in props.get("entities", [])]
        for entity_id in entity_ids:
            entity = entities.get(entity_id)
            name = entity_name(entity) if entity else ""
            if not entity or not EXIT_NAME_PATTERN.fullmatch(name):
                report["skipped_exits"].append(
                    {"geometry_id": feature["id"], "entity_id": entity_id, "name": name}
                )
                continue
            existing = exit_by_entity.get(entity_id)
            if existing is None:
                exit_by_entity[entity_id] = feature
            else:
                warnings.append(
                    f"Exit entity {entity_id} has multiple 1F entrance markers; "
                    "first marker retained"
                )

    for entity_id, feature in exit_by_entity.items():
        entity = entities[entity_id]
        name = entity_name(entity)
        location = feature.get("location")
        if not location:
            geometry = shape(feature["geometry"])
            point = geometry.representative_point()
            lon, lat = float(point.x), float(point.y)
        else:
            lon, lat = [float(value) for value in location["coordinates"][:2]]
        node_id, snap_distance = nearest_node(lon, lat, "1F", nodes)
        if snap_distance > max_snap_m:
            warnings.append(
                f"Exit {name} skipped: snap distance {snap_distance:.1f}m exceeds {max_snap_m:.1f}m"
            )
            continue
        places.append(
            {
                "id": f"exit-{entity_id}",
                "type": "exit",
                "name": f"{name}出口",
                "operator": "公開データに事業者記載なし",
                "direction": "地上出入口",
                "floor": "1F",
                "lon": round(lon, 7),
                "lat": round(lat, 7),
                "node_id": node_id,
                "snap_distance_m": round(snap_distance, 2),
                "source_entity_id": entity_id,
                "source_geometry_id": int(feature["id"]),
                "verified_on_site": False,
            }
        )

    return places, warnings, report


def apply_place_overrides(places: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    if not OVERRIDES_PATH.is_file():
        return places, warnings
    by_source = {
        (str(place["source_entity_id"]), str(place["type"])): place for place in places
    }
    with OVERRIDES_PATH.open(encoding="utf-8-sig", newline="") as handle:
        for line_number, row in enumerate(csv.DictReader(handle), start=2):
            if not row or not str(row.get("source_entity_id", "")).strip():
                continue
            evidence = str(row.get("evidence_url", "")).strip()
            note = str(row.get("note", "")).strip()
            if not evidence or not note:
                raise ValueError(
                    f"Override line {line_number} requires evidence_url and note"
                )
            key = (
                str(row["source_entity_id"]).strip(),
                str(row.get("place_type", "")).strip(),
            )
            place = by_source.get(key)
            if place is None:
                warnings.append(f"Override line {line_number} did not match a place")
                continue
            action = str(row.get("action", "update")).strip().lower()
            if action == "exclude":
                place["_excluded"] = True
                continue
            if action != "update":
                raise ValueError(f"Override line {line_number} has invalid action {action!r}")
            for field in ("name", "operator", "direction", "floor", "node_id"):
                value = str(row.get(field, "")).strip()
                if value:
                    place[field] = value
            for field in ("lon", "lat"):
                value = str(row.get(field, "")).strip()
                if value:
                    place[field] = float(value)
            place["verified_on_site"] = (
                str(row.get("verified_on_site", "")).strip().lower() == "true"
            )
            place["override_evidence_url"] = evidence
            place["override_verified_at"] = str(row.get("verified_at", "")).strip() or None
            place["override_note"] = note
    return [place for place in places if not place.pop("_excluded", False)], warnings


def build_floor_map(
    geometry_by_floor: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    selected: list[dict[str, Any]] = []
    allowed = {"hallway", "stairs", "escalator", "elevator", "ramp", "movingwalkway"}
    for floor, features in geometry_by_floor.items():
        for feature in features:
            facility = facility_type(feature)
            if facility not in allowed:
                continue
            geometry = shape(feature["geometry"])
            if geometry.is_empty:
                continue
            simplified = geometry.simplify(0.0000015, preserve_topology=True)
            selected.append(
                {
                    "type": "Feature",
                    "properties": {
                        "id": str(feature["id"]),
                        "floor": floor,
                        "facility": facility,
                        "display_name": feature.get("properties", {}).get("display_name"),
                    },
                    "geometry": simplified.__geo_interface__,
                }
            )
    frame = gpd.GeoDataFrame.from_features(selected, crs="EPSG:4326")
    if frame.crs is None or frame.crs.to_epsg() != 4326:
        raise ValueError("Floor map CRS must be EPSG:4326")
    return json.loads(frame.to_json(drop_id=True))


def build_landmarks(
    nodes: dict[str, dict[str, Any]],
    links: dict[str, Any],
) -> list[dict[str, Any]]:
    degree: Counter[str] = Counter()
    for feature in links["features"]:
        degree[str(feature["properties"]["source"])] += 1
        degree[str(feature["properties"]["target"])] += 1
    landmarks: list[dict[str, Any]] = []
    for node_id, count in degree.items():
        node = nodes[node_id]
        facility = str(node.get("facility") or "")
        if count < 3 and facility not in KNOWN_FACILITIES:
            continue
        if facility in {"stairs", "escalator", "elevator", "ramp", "movingwalkway"}:
            label = {
                "stairs": "階段",
                "escalator": "エスカレーター",
                "elevator": "エレベーター",
                "ramp": "スロープ",
                "movingwalkway": "動く歩道",
            }[facility]
            description = f"公開階層図形に記録された{label}です。"
        else:
            label = "主要分岐"
            description = "Nav Link が3本以上接続する分岐です。"
        landmarks.append(
            {
                "id": f"landmark-{node_id}",
                "node_id": node_id,
                "name": label,
                "description": description,
                "floor": node["floor"],
                "lon": round(float(node["lon"]), 7),
                "lat": round(float(node["lat"]), 7),
                "photo_url": None,
                "plateau_url": None,
                "is_sample": False,
            }
        )
    return landmarks


def write_json(filename: str, payload: Any) -> None:
    (OUTPUT_DIR / filename).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="東京都新宿駅データをアプリ用に正規化します。")
    parser.add_argument("--max-snap-m", type=float, default=50.0)
    args = parser.parse_args()
    if args.max_snap_m <= 0:
        parser.error("--max-snap-m must be positive")
    if not ZIP_PATH.is_file() or not RAW_MANIFEST_PATH.is_file():
        raise FileNotFoundError("Run scripts/fetch_open_data.py before normalization")

    raw_manifest = json.loads(RAW_MANIFEST_PATH.read_text(encoding="utf-8"))
    with zipfile.ZipFile(ZIP_PATH) as archive:
        nav = read_zip_json(archive, "v5_nav.json")
        community_map = read_zip_json(archive, "com-map.geojson")
        community_entities = read_zip_json(archive, "com-entity.geojson")
        if nav.get("ft") != "navnet5":
            raise ValueError(f"Unsupported Nav format: {nav.get('ft')!r}")
        if int(nav["id"]) != int(community_map["id"]):
            raise ValueError("Nav and Community Map IDs differ")
        if int(nav["v"]) != int(community_map["map_version"]):
            raise ValueError("Nav and Community Map versions differ")

        level_names = {
            int(level["id"]): normalize_floor(str(level["properties"]["name"]))
            for level in community_map["drawings"][0]["levels"]
        }
        geometry_by_id, geometry_by_floor, warnings = load_level_geometries(
            archive, level_names
        )
        nodes_geojson, nodes, node_warnings = transform_nodes(
            nav, community_map, geometry_by_id
        )
        warnings.extend(node_warnings)
        links_geojson, link_warnings = transform_links(nav, nodes)
        warnings.extend(link_warnings)
        entities = {
            int(entity["id"]): entity
            for entity in community_entities.get("entities", [])
        }
        places, place_warnings, classification_report = build_places(
            entities,
            geometry_by_id,
            geometry_by_floor,
            nodes,
            args.max_snap_m,
        )
        warnings.extend(place_warnings)
        places, override_warnings = apply_place_overrides(places)
        warnings.extend(override_warnings)
        floor_map = build_floor_map(geometry_by_floor)

    if not any(place["type"] == "gate" for place in places):
        raise ValueError("No gates were classified from public data")
    if not any(place["type"] == "exit" for place in places):
        raise ValueError("No exits were classified from public data")

    landmarks = build_landmarks(nodes, links_geojson)
    floors = sorted({node["floor"] for node in nodes.values()}, key=floor_sort_key)
    raw_zip = next(
        resource
        for resource in raw_manifest["resources"]
        if resource["filename"] == ZIP_PATH.name
    )
    generated_at = datetime.now(UTC).isoformat()
    manifest = {
        "data_mode": "open-data",
        "title": raw_manifest["dataset"]["title"],
        "provider": raw_manifest["dataset"]["provider"],
        "catalog_url": raw_manifest["dataset"]["catalog_url"],
        "license": raw_manifest["dataset"]["license"],
        "license_url": raw_manifest["dataset"]["license_url"],
        "specification_revision": raw_manifest["dataset"]["specification_revision"],
        "generated_at": generated_at,
        "crs": "EPSG:4326",
        "distance_unit": "meter",
        "raw_resource": raw_zip,
        "source_community_id": int(nav["id"]),
        "source_map_version": int(nav["v"]),
        "node_count": len(nodes_geojson["features"]),
        "link_count": len(links_geojson["features"]),
        "gate_count": sum(place["type"] == "gate" for place in places),
        "exit_count": sum(place["type"] == "exit" for place in places),
        "landmark_count": len(landmarks),
        "floors": floors,
        "warnings": sorted(set(warnings)),
        "transformation": {
            "max_snap_m": args.max_snap_m,
            "node_coordinates": "Nav Mercator -> drawing affine -> WGS84 affine",
            "link_distance": "public dm; WGS84 geodesic only for invalid/missing dm",
            "unknown_floors": "rejected",
            "manual_overrides": str(OVERRIDES_PATH.relative_to(PROJECT_ROOT)),
        },
    }
    classification_report.update(
        {
            "generated_at": generated_at,
            "classified_gate_count": manifest["gate_count"],
            "classified_exit_count": manifest["exit_count"],
        }
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_json("nodes.geojson", nodes_geojson)
    write_json("links.geojson", links_geojson)
    write_json("places.json", sorted(places, key=lambda place: (place["type"], place["name"])))
    write_json("landmarks.json", landmarks)
    write_json("floor_map.geojson", floor_map)
    write_json("classification-report.json", classification_report)
    write_json("manifest.json", manifest)
    print(
        "Built open-data bundle: "
        f"{manifest['node_count']} nodes, {manifest['link_count']} links, "
        f"{manifest['gate_count']} gates, {manifest['exit_count']} exits"
    )
    print(f"Warnings: {len(manifest['warnings'])}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
