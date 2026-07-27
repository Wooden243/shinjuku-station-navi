from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from normalize_open_data import operator_from_public_name, transform_links  # noqa: E402


def test_operator_prefers_explicit_railway_name_over_incidental_jr_text() -> None:
    assert operator_from_public_name("都営大江戸線 JR方面改札口") == "東京都交通局"
    assert operator_from_public_name("小田急線 南口JR連絡口") == "小田急電鉄"


def test_zero_length_self_loop_is_not_emitted() -> None:
    nav = {
        "l": [
            {"id": 1, "n1": 10, "n2": 10, "d": 3, "dm": 0},
        ]
    }
    nodes = {
        "10": {
            "id": "10",
            "floor": "B1",
            "lon": 139.7,
            "lat": 35.69,
            "facility": None,
        }
    }
    links, warnings = transform_links(nav, nodes)
    assert links["features"] == []
    assert any("self-loop" in warning for warning in warnings)


def test_public_zero_length_vertical_link_is_retained_without_fabricated_distance() -> None:
    nav = {
        "l": [
            {"id": 2, "n1": 10, "n2": 11, "d": 3, "dm": 0, "dz": 1},
        ]
    }
    nodes = {
        "10": {
            "id": "10",
            "floor": "B1",
            "lon": 139.7,
            "lat": 35.69,
            "facility": "elevator",
        },
        "11": {
            "id": "11",
            "floor": "1F",
            "lon": 139.7,
            "lat": 35.69,
            "facility": "elevator",
        },
    }
    links, warnings = transform_links(nav, nodes)
    properties = links["features"][0]["properties"]
    assert properties["length_m"] == 0
    assert properties["length_source"] == "public-dm-zero-vertical"
    assert any("zero-meter vertical" in warning for warning in warnings)

